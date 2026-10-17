"""Plans, estimates and executes experiment runs, with a cost gate, a project budget cap and resume.

Spend safety: every paid call is estimated before the run, the whole estimate must fit the remaining
project budget, and during the run the next case is skipped (run marked `partial`) if it could push
spend past the budget. A case's result and its ledger rows are written in one transaction.
"""
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ValidationError

from evallab.adapters import get_system
from evallab.adapters.base import RAGSystem, Trace
from evallab.cache import DiskCache
from evallab.config import Settings
from evallab.datasets import Case, Dataset, load_dataset, subset
from evallab.experiments import Experiment, ExperimentError, expand, experiment_git_state, load_experiment, run_id
from evallab.metrics import answer, retrieval
from evallab.metrics.judge import Judge, make_judge
from evallab.pricing import Pricing
from evallab.pricing import load as load_pricing
from evallab.stats import paired_bootstrap_ci
from evallab.store import RunRecord, Store, now

DEGRADED_ERROR_SHARE = 0.10
HEURISTIC_OUTPUT_TOKENS = {"system": 1500, "judge": 300}  # thinking tokens bill as output
HEURISTIC_JUDGE_INPUT_TOKENS = 1500


class RunRefused(ExperimentError):
    """The run was not started; the message says why."""


@dataclass
class PlannedRun:
    experiment: Experiment
    exp_text: str
    exp_sha: str
    exp_dirty: bool
    label: str
    run_id: str
    config: BaseModel
    dataset: Dataset
    cases: list[Case]
    existing: RunRecord | None
    skip: bool


@dataclass
class Estimate:
    label: str
    run_id: str
    cases: int
    uncached_system: int
    uncached_judge: int
    usd: float
    measured: bool


@dataclass
class RunOutcome:
    planned: list[PlannedRun]
    estimates: list[Estimate] = field(default_factory=list)
    records: list[RunRecord] = field(default_factory=list)


def _judge_identity(exp: Experiment, settings: Settings) -> tuple[str, str]:
    return (settings.judge_model, settings.judge_rubric_version) if exp.judge else ("none", "none")


def plan_runs(exp_path: Path, settings: Settings, store: Store, system: RAGSystem, force: bool = False) -> list[PlannedRun]:
    exp, text = load_experiment(exp_path)
    sha, dirty = experiment_git_state(exp_path)
    ds = load_dataset(exp.dataset, settings)
    try:
        cases = subset(ds, exp.subset)
    except ValueError as e:
        raise ExperimentError(f"{exp.name}: {e}") from e
    schema = system.config_schema()
    judge_model, rubric = _judge_identity(exp, settings)
    planned = []
    for label, raw in expand(exp):
        try:
            config = schema(**raw)
        except ValidationError as e:
            err = e.errors()[0]
            where = ".".join(str(p) for p in err["loc"])
            raise ExperimentError(f"{exp.name} [{label}]: {where}: {err['msg']}") from e
        rid = run_id(ds.sha256, exp.subset, ds.corpus.lock_hash, system.version(), judge_model, rubric,
                     config.model_dump(), 0)
        try:
            existing = store.get_run(rid)
        except KeyError:
            existing = None
        skip = existing is not None and existing.status in ("complete", "degraded") and not force
        planned.append(PlannedRun(exp, text, sha, dirty, label, rid, config, ds, cases, existing, skip))
    return planned


def per_call_cost(store: Store, pricing: Pricing, model: str, role: str, config: BaseModel) -> tuple[float, bool]:
    """Mean actual cost of earlier calls with this model and role, else a deliberately high heuristic."""
    rows = [r["usd"] for r in store.ledger_rows() if r["model"] == model and r["role"] == role]
    if rows:
        return sum(rows) / len(rows), True
    if role == "system":
        inp = (getattr(config, "top_k", 8) * getattr(config, "chunk_chars", 2000) + 600) // 4
    else:
        inp = HEURISTIC_JUDGE_INPUT_TOKENS
    return pricing.cost(model, inp, HEURISTIC_OUTPUT_TOKENS[role]), False


def _todo(p: PlannedRun, store: Store, resume: bool) -> list[Case]:
    done = store.done_case_ids(p.run_id) if resume and p.existing is not None else set()
    return [c for c in p.cases if c.id not in done]


def estimate(p: PlannedRun, store: Store, pricing: Pricing, system: RAGSystem, judge: Judge, resume: bool) -> Estimate:
    todo = _todo(p, store, resume)
    if not p.experiment.llm:
        return Estimate(p.label, p.run_id, len(todo), 0, 0, 0.0, True)
    system.prepare(p.dataset.corpus, p.config)
    n_sys = sum(1 for c in todo if not system.would_hit_cache(c.question, p.config))
    # The judge's cache key depends on the answer, unknown before running: assume a cached answer
    # also has a cached verdict. The in-run budget check backs this up.
    n_judge = n_sys if p.experiment.judge else 0
    c_sys, m_sys = per_call_cost(store, pricing, p.config.model, "system", p.config)
    c_judge, m_judge = per_call_cost(store, pricing, judge.model, "judge", p.config) if n_judge else (0.0, True)
    return Estimate(p.label, p.run_id, len(todo), n_sys, n_judge, n_sys * c_sys + n_judge * c_judge,
                    (m_sys or not n_sys) and (m_judge or not n_judge))


def _cited_texts(trace: Trace) -> list[str]:
    by_rank = {c.rank: c.text for c in trace.retrieved}
    seen, out = set(), []
    for c in trace.citations:
        if c.chunk_rank in by_rank and c.chunk_rank not in seen:
            seen.add(c.chunk_rank)
            out.append(by_rank[c.chunk_rank])
    return out


def _run_case(p: PlannedRun, case: Case, system: RAGSystem, judge: Judge, pricing: Pricing):
    exp, cfg = p.experiment, p.config
    t0 = time.perf_counter()
    trace = system.answer(case.question, cfg, llm=exp.llm)
    latency = round((time.perf_counter() - t0) * 1000)
    k = getattr(cfg, "top_k", 8)
    judged = exp.judge and trace.status in ("answered", "partial")
    verdict, jcall = (judge.judge(case, trace, _cited_texts(trace)) if judged else (None, None))
    metrics = retrieval.case_metrics(trace, case, k)
    if exp.llm:
        metrics |= answer.case_metrics(trace, case, verdict, judged)
    ledger, cost = [], {"cost_spent_system": 0.0, "cost_spent_judge": 0.0,
                        "cost_nominal_system": 0.0, "cost_nominal_judge": 0.0}
    for call in [*trace.llm_calls, *([jcall] if jcall else [])]:
        usd = pricing.cost(call.model, call.input_tokens, call.output_tokens)
        cost[f"cost_nominal_{call.role}"] += usd
        if not call.cached:
            cost[f"cost_spent_{call.role}"] += usd
            ledger.append((call.model, call.role, usd))
    row = {
        "case_id": case.id, "tag": case.tag, "answerable": case.answerable, "status": "ok",
        "pass": answer.case_pass(trace, case, verdict, exp.llm, k), "metrics": metrics,
        "trace": trace.to_dict(), "judge": asdict(verdict) if verdict else None, "error": None,
        "latency_ms": latency, "cached": bool(trace.llm_calls) and all(c.cached for c in trace.llm_calls),
        **cost,
    }
    return row, ledger


def _error_row(case: Case, err: Exception) -> dict:
    return {"case_id": case.id, "tag": case.tag, "answerable": case.answerable, "status": "error", "pass": None,
            "metrics": {}, "trace": None, "judge": None, "error": f"{type(err).__name__}: {err}",
            "latency_ms": None, "cached": False, "cost_spent_system": 0.0, "cost_spent_judge": 0.0,
            "cost_nominal_system": 0.0, "cost_nominal_judge": 0.0}


def execute(p: PlannedRun, settings: Settings, store: Store, system: RAGSystem, judge: Judge, pricing: Pricing,
            budget_remaining: float, per_case_usd: float, resume: bool = False) -> RunRecord:
    exp = p.experiment
    if resume and p.existing is not None:
        store.set_status(p.run_id, "running")
    else:
        judge_model, _ = _judge_identity(exp, settings)
        store.create_run(RunRecord(
            run_id=p.run_id, experiment=exp.name, label=p.label, config=p.config.model_dump(), system=exp.system,
            system_version=system.version(), dataset=p.dataset.ref, dataset_sha=p.dataset.sha256,
            subset=exp.subset, judge_model=judge_model, status="running", started_at=now()))
    system.prepare(p.dataset.corpus, p.config)
    spent, stopped = 0.0, False
    for case in _todo(p, store, resume):
        if exp.llm and spent + per_case_usd > budget_remaining + 1e-12:
            stopped = True
            break
        try:
            row, ledger = _run_case(p, case, system, judge, pricing)
        except KeyboardInterrupt:
            store.set_status(p.run_id, "partial")
            raise
        except Exception as e:  # one broken case must not sink the run; it is stored and counted
            row, ledger = _error_row(case, e), []
        store.put_case(p.run_id, row, ledger)
        spent += sum(usd for _, _, usd in ledger)
    rows = store.case_rows(p.run_id)
    summary = answer.summarize(rows, exp.llm)
    passes = [float(r["pass"]) for r in rows if r["status"] == "ok" and r["pass"] is not None]
    _, lo, hi = paired_bootstrap_ci([0.0] * len(passes), passes)
    summary["accuracy_ci"] = [lo, hi]
    if stopped or len(rows) < len(p.cases):
        status = "partial"
    elif summary["n_errored"] > DEGRADED_ERROR_SHARE * len(rows):
        status = "degraded"
    else:
        status = "complete"
    store.finish_run(p.run_id, status, summary)
    return store.get_run(p.run_id)


def format_estimates(estimates: list[Estimate]) -> str:
    head = f"{'run':<34} {'run_id':<12} {'cases':>5} {'uncached sys':>12} {'uncached judge':>14} {'est. USD':>9}  measured"
    lines = [head, "-" * len(head)]
    for e in estimates:
        lines.append(f"{e.label[:34]:<34} {e.run_id:<12} {e.cases:>5} {e.uncached_system:>12} {e.uncached_judge:>14} "
                     f"{e.usd:>9.4f}  {'yes' if e.measured else 'no (heuristic)'}")
    return "\n".join(lines)


def run_experiment(path: Path, settings: Settings, store: Store, *, system: RAGSystem | None = None,
                   judge: Judge | None = None, pricing: Pricing | None = None, yes: bool = False,
                   dry_run: bool = False, force: bool = False, resume: bool = False,
                   confirm: Callable[[str], bool] | None = None, echo: Callable[[str], None] = print) -> RunOutcome:
    exp, _ = load_experiment(path)
    system = system or get_system(exp.system, settings)
    judge = judge or make_judge(settings, DiskCache(settings.cache_dir / "judge"))
    pricing = pricing or load_pricing(settings.root / "pricing.yaml")
    planned = plan_runs(path, settings, store, system, force=force)
    out = RunOutcome(planned)
    if planned[0].exp_dirty:
        raise RunRefused(f"{Path(path).name} has uncommitted changes; commit it first so the hypothesis predates the results")
    for p in planned:
        if p.existing is not None and p.existing.status in ("partial", "running") and not (resume or force):
            raise RunRefused(f"Run {p.run_id} ({p.label}) is {p.existing.status}; use --resume to continue or --force to restart")
    todo = [p for p in planned if not p.skip]
    for p in planned:
        if p.skip:
            echo(f"{p.label}: already complete as {p.run_id} (use --force to re-run)")
    if not todo:
        if not dry_run:
            _link_all(store, exp, planned)
        return out
    out.estimates = [estimate(p, store, pricing, system, judge, resume) for p in todo]
    spent = store.spent_total()
    remaining = settings.budget_total_usd - spent
    total = sum(e.usd for e in out.estimates)
    echo(format_estimates(out.estimates))
    echo(f"Total estimate ${total:.4f} · project spend: spent ${spent:.2f} of ${settings.budget_total_usd:.2f}, "
         f"remaining ${remaining:.2f}")
    if total > remaining + 1e-12:
        raise RunRefused(f"Estimated ${total:.4f} exceeds the remaining budget ${remaining:.4f}; nothing was run")
    if not settings.anthropic_api_key:
        n_sys = sum(e.uncached_system for e in out.estimates) if getattr(system, "needs_api_key", True) else 0
        n_judge = sum(e.uncached_judge for e in out.estimates) if getattr(judge, "needs_api_key", True) else 0
        if n_sys or n_judge:
            raise RunRefused(f"ANTHROPIC_API_KEY is not set and {n_sys + n_judge} uncached calls need it")
    if dry_run:
        return out
    if total > 0 and not yes and not (confirm and confirm(f"Run this for ~${total:.4f}?")):
        raise RunRefused("Declined; nothing was run")
    _link_all(store, exp, planned)
    for p, e in zip(todo, out.estimates):
        per_case = e.usd / e.uncached_system if e.uncached_system else 0.0
        remaining = settings.budget_total_usd - store.spent_total()
        rec = execute(p, settings, store, system, judge, pricing, remaining, per_case,
                      resume=resume and p.existing is not None)
        out.records.append(rec)
        echo(f"{rec.label}: {rec.status} ({rec.run_id}) accuracy={_fmt(rec.summary.get('accuracy'))} "
             f"spent=${rec.summary['cost_spent']:.4f}")
    return out


def _link_all(store: Store, exp: Experiment, planned: list[PlannedRun]) -> None:
    store.upsert_experiment(exp.name, planned[0].exp_text, planned[0].exp_sha, exp.hypothesis)
    for p in planned:
        store.link_run(exp.name, p.label, p.run_id)


def _fmt(v) -> str:
    return "—" if v is None else f"{v:.3f}"
