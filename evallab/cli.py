"""`evallab` command line. Commands are thin wrappers over the library modules."""
from pathlib import Path

import typer

from evallab import __version__
from evallab.config import load_settings

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Evaluate and regression-test RAG systems.")
dataset_app = typer.Typer(no_args_is_help=True, help="Create, version and validate datasets.")
app.add_typer(dataset_app, name="dataset")


class UserError(Exception):
    """Raised for problems the user can fix; printed as one line, exit code 2."""


def fail(message: str, code: int = 2) -> None:
    typer.echo(message.splitlines()[0] if message else "error", err=True)
    raise typer.Exit(code)


def run_guarded(fn):
    """Map user-facing errors from the library to a one-line message and exit code 2."""
    from evallab.datasets import DatasetError
    from evallab.experiments import ExperimentError

    try:
        return fn()
    except (DatasetError, ExperimentError, UserError, FileNotFoundError, KeyError, ValueError) as e:
        fail(str(e).strip("'\""))


@app.callback()
def main() -> None:
    """Evaluate and regression-test RAG systems."""


@app.command()
def version() -> None:
    """Print the evallab version."""
    typer.echo(__version__)


@dataset_app.command("import")
def dataset_import(
    name: str,
    source: Path = typer.Option(..., "--from", help="Source JSONL file"),
    corpus: Path = typer.Option(..., "--corpus", help="Directory of corpus documents"),
    changes: str = typer.Option(..., "--changes", help="Changelog line for v1"),
) -> None:
    """Import a JSONL question file as version v1 of a new dataset."""
    from evallab.datasets import import_dataset

    ds = run_guarded(lambda: import_dataset(name, source, corpus, changes, load_settings()))
    typer.echo(f"{ds.ref}: {len(ds.cases)} cases, valid")


@dataset_app.command("validate")
def dataset_validate(ref: str) -> None:
    """Verify hashes, corpus lock and case validity of NAME@VERSION."""
    from evallab.datasets import load_dataset

    ds = run_guarded(lambda: load_dataset(ref, load_settings()))
    typer.echo(f"{ds.ref}: {len(ds.cases)} cases, valid")


@dataset_app.command("new")
def dataset_new(name: str, from_version: str = typer.Option(..., "--from")) -> None:
    """Start an editable draft from an existing version."""
    from evallab.datasets import new_draft

    path = run_guarded(lambda: new_draft(name, from_version, load_settings()))
    typer.echo(f"Draft written to {path}; edit it, then run `evallab dataset publish {name} --changes ...`")


@dataset_app.command("publish")
def dataset_publish(name: str, changes: str = typer.Option(..., "--changes")) -> None:
    """Validate the draft and publish it as the next version."""
    from evallab.datasets import publish

    ds = run_guarded(lambda: publish(name, changes, load_settings()))
    typer.echo(f"Published {ds.ref}: {len(ds.cases)} cases")


@dataset_app.command("list")
def dataset_list() -> None:
    """List datasets and their versions."""
    from evallab.datasets import list_datasets

    for m in list_datasets(load_settings()):
        for v in m["versions"]:
            typer.echo(f"{m['name']}@{v['version']}  {v['cases']} cases  {v['created']}  {v['changes']}")


def _store(settings):
    from evallab.store import Store

    return Store(settings.store_path)


@app.command()
def run(
    path: Path,
    yes: bool = typer.Option(False, "--yes", help="Skip the spend confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the estimate and stop"),
    force: bool = typer.Option(False, "--force", help="Re-run runs that already completed"),
    resume: bool = typer.Option(False, "--resume", help="Continue partial runs"),
) -> None:
    """Run an experiment file (shows a cost estimate first)."""
    from evallab.runner import run_experiment

    settings = load_settings()
    run_guarded(lambda: run_experiment(path, settings, _store(settings), yes=yes, dry_run=dry_run, force=force,
                                       resume=resume, confirm=lambda m: typer.confirm(m, default=False),
                                       echo=typer.echo))


@app.command()
def budget() -> None:
    """Show project API spend against the budget."""
    settings = load_settings()
    spent = _store(settings).spent_total()
    total = settings.budget_total_usd
    typer.echo(f"spent ${spent:.2f} of ${total:.2f} (remaining ${total - spent:.2f})")


@app.command("list")
def list_runs(experiment: str = typer.Option(None, "--experiment")) -> None:
    """List runs in the results store."""
    for r in _store(load_settings()).list_runs(experiment):
        acc = (r.summary or {}).get("accuracy")
        typer.echo(f"{r.run_id}  {r.experiment}:{r.label}  {r.status}  "
                   f"accuracy={'—' if acc is None else f'{acc:.3f}'}  {r.started_at}")


def _resolve_run(store, ref: str):
    """`experiment:label` (latest run linked under that label) or a run-id prefix."""
    if ":" in ref:
        experiment, label = ref.split(":", 1)
        run = store.find_run(experiment, label)
        if run is None:
            raise UserError(f"No run labelled {label!r} in experiment {experiment!r}")
        return run, experiment
    run = store.get_run(ref)
    return run, run.experiment


def _rows_with_questions(store, settings, run) -> list[dict]:
    from evallab.datasets import DatasetError, load_dataset

    rows = store.case_rows(run.run_id)
    try:
        questions = {c.id: c.question for c in load_dataset(run.dataset, settings).cases}
    except DatasetError:
        questions = {}
    for r in rows:
        r["question"] = questions.get(r["case_id"])
    return rows


def run_dict(run) -> dict:
    from dataclasses import asdict

    return asdict(run)


@app.command()
def compare(
    base: str,
    cand: str,
    fmt: str = typer.Option("md", "--format", help="md or json"),
    out: Path = typer.Option(None, "--out", help="Write the report to a file"),
    gate: bool = typer.Option(False, "--gate", help="Exit 1 if the candidate fails the gate"),
    allow_incomplete: bool = typer.Option(False, "--allow-incomplete"),
    max_regressed: int = typer.Option(None, "--max-regressed"),
    min_accuracy_delta: float = typer.Option(None, "--min-accuracy-delta"),
    max_cost_ratio: float = typer.Option(None, "--max-cost-ratio"),
) -> None:
    """Compare two runs case by case (BASE and CAND: run-id prefix or experiment:label)."""
    import json

    import yaml

    from evallab.compare import check_gate, compare_runs, render_markdown
    from evallab.experiments import GateSpec

    settings = load_settings()
    store = _store(settings)

    def build():
        b, _ = _resolve_run(store, base)
        c, c_exp = _resolve_run(store, cand)
        report = compare_runs(run_dict(b), _rows_with_questions(store, settings, b),
                              run_dict(c), _rows_with_questions(store, settings, c), allow_incomplete)
        exp = store.get_experiment(c_exp)
        spec = GateSpec(**((yaml.safe_load(exp["yaml"]) or {}).get("gate") or {})) if exp else GateSpec()
        overrides = {"max_regressed": max_regressed, "min_accuracy_delta": min_accuracy_delta,
                     "max_cost_ratio": max_cost_ratio}
        spec = spec.model_copy(update={k: v for k, v in overrides.items() if v is not None})
        return report, spec

    report, spec = run_guarded(build)
    text = json.dumps(report, indent=1, sort_keys=True) if fmt == "json" else render_markdown(report)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
    else:
        typer.echo(text)
    if gate:
        fails = check_gate(report, spec)
        for f in fails:
            typer.echo(f"GATE FAIL: {f}", err=True)
        if fails:
            raise typer.Exit(1)
        typer.echo("GATE PASS", err=True)


@app.command("ci-baseline")
def ci_baseline() -> None:
    """Print the baseline run id used by CI (evallab.toml [ci] baseline_run)."""
    run_id = load_settings().ci_baseline_run
    if not run_id:
        fail("No [ci] baseline_run set in evallab.toml")
    typer.echo(run_id)


spot_app = typer.Typer(no_args_is_help=True, help="Check the judge against hand labels.")
app.add_typer(spot_app, name="spotcheck")


@spot_app.command("sample")
def spotcheck_sample(run_ids: list[str], n: int = typer.Option(30, "--n")) -> None:
    """Write a CSV of judged cases, stratified by model, for hand labelling."""
    from evallab.spotcheck import sample

    settings = load_settings()
    path = run_guarded(lambda: sample(_store(settings), settings, run_ids, n=n))
    typer.echo(f"Wrote {path}; fill human_correct (yes/no) and human_unsupported, then run `evallab spotcheck score {path}`")


@spot_app.command("score")
def spotcheck_score(csv_path: Path) -> None:
    """Judge-vs-human agreement and Cohen's kappa from a labelled CSV."""
    import json

    from evallab.spotcheck import score

    typer.echo(json.dumps(run_guarded(lambda: score(csv_path)), indent=1))
