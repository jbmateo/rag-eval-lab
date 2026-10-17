import pytest
from typer.testing import CliRunner

from evallab import pricing as pricing_mod
from evallab.adapters.fake import FakeSystem
from evallab.experiments import ExperimentError
from evallab.metrics.judge import FakeJudge
from evallab.runner import RunRefused, execute, plan_runs, run_experiment
from evallab.store import Store
from tests.conftest import FIXTURES

PRICING = pricing_mod.load(FIXTURES.parent.parent / "pricing.yaml")

LLM_EXP = """name: sweep
system: fake
dataset: drones@v1
llm: true
judge: true
hypothesis: higher quality passes more cases
grid: {quality: [0.4, 0.9]}
"""
FREE_EXP = """name: free
system: fake
dataset: drones@v1
grid: {quality: [0.4, 0.9]}
"""


class NeedsKey(FakeSystem):
    needs_api_key = True


class InterruptOnce(FakeSystem):
    def __init__(self, at: int):
        super().__init__()
        self.at, self.calls, self.fired = at, 0, False

    def answer(self, question, config, llm):
        self.calls += 1
        if self.calls == self.at and not self.fired:
            self.fired = True
            raise KeyboardInterrupt
        return super().answer(question, config, llm)


@pytest.fixture
def store(git_lab):
    return Store(git_lab.store_path)


def go(path, settings, store, system=None, **kw):
    return run_experiment(path, settings, store, system=system or FakeSystem(), judge=FakeJudge(),
                          pricing=PRICING, yes=True, echo=lambda *_: None, **kw)


def test_free_run_completes_and_is_reused(write_experiment, git_lab, store):
    p = write_experiment("free", FREE_EXP)
    out = go(p, git_lab, store)
    assert [r.status for r in out.records] == ["complete", "complete"]
    assert all(len(store.case_rows(r.run_id)) == 20 for r in out.records)
    assert store.spent_total() == 0.0
    again = go(p, git_lab, store)
    assert again.records == [] and all(pr.skip for pr in again.planned)
    forced = go(p, git_lab, store, force=True)
    assert len(forced.records) == 2


def test_llm_run_bills_ledger(write_experiment, git_lab, store):
    out = go(write_experiment("sweep", LLM_EXP), git_lab, store)
    rows = [row for r in out.records for row in store.case_rows(r.run_id)]
    calls = sum(row["cost_spent_system"] > 0 for row in rows) + sum(row["cost_spent_judge"] > 0 for row in rows)
    assert len(store.ledger_rows()) == calls > 20
    assert abs(store.spent_total() - sum(r.summary["cost_spent"] for r in out.records)) < 1e-12
    assert out.records[1].summary["accuracy"] >= out.records[0].summary["accuracy"]


def test_invalid_config_rejected(write_experiment, git_lab, store):
    p = write_experiment("bad", FREE_EXP.replace("name: free", "name: bad").replace("quality: [0.4, 0.9]", "nope: [1]"))
    with pytest.raises(ExperimentError, match="nope"):
        go(p, git_lab, store)
    assert store.list_runs() == []


def test_unknown_system_or_dataset(write_experiment, git_lab, store):
    p = write_experiment("x", FREE_EXP.replace("drones@v1", "drones@v9"))
    with pytest.raises(Exception, match="available: v1"):
        run_experiment(p, git_lab, store, pricing=PRICING, yes=True, echo=lambda *_: None)


def test_dirty_experiment_refused(write_experiment, git_lab, store):
    p = write_experiment("free", FREE_EXP)
    p.write_text(FREE_EXP + "# changed\n")
    with pytest.raises(RunRefused, match="uncommitted"):
        go(p, git_lab, store)


def test_estimate_over_budget_refused(write_experiment, git_lab, store):
    settings = git_lab.model_copy(update={"budget_total_usd": 0.0001})
    with pytest.raises(RunRefused, match="budget"):
        go(write_experiment("sweep", LLM_EXP), settings, store)
    assert store.list_runs() == []


def test_budget_stop_marks_partial(write_experiment, git_lab, store):
    p = write_experiment("sweep", LLM_EXP)
    planned = plan_runs(p, git_lab, store, FakeSystem())[0]
    rec = execute(planned, git_lab, store, FakeSystem(), FakeJudge(), PRICING,
                  budget_remaining=0.004, per_case_usd=0.00175)
    assert rec.status == "partial"
    assert 0 < len(store.case_rows(rec.run_id)) < 20
    assert store.spent_total() <= 0.004


def test_case_exception_is_error_and_degraded(write_experiment, git_lab, store, fixture_questions):
    qs = [q["question"] for q in fixture_questions[:3]]
    p = write_experiment("err", FREE_EXP.replace("name: free", "name: err") + f"base: {{raise_on: {qs!r}}}\n")
    out = go(p, git_lab, store)
    rows = store.case_rows(out.records[0].run_id)
    assert out.records[0].status == "degraded"
    assert sum(r["status"] == "error" for r in rows) == 3 and all(r["error"] for r in rows if r["status"] == "error")


def test_interrupt_then_resume(write_experiment, git_lab, store):
    p = write_experiment("sweep", LLM_EXP)
    with pytest.raises(KeyboardInterrupt):
        go(p, git_lab, store, system=InterruptOnce(at=5))
    run = store.list_runs()[0]
    assert run.status == "partial" and len(store.case_rows(run.run_id)) == 4
    with pytest.raises(RunRefused, match="--resume"):
        go(p, git_lab, store)
    go(p, git_lab, store, resume=True)
    rows = store.case_rows(run.run_id)
    assert len(rows) == 20 and store.get_run(run.run_id).status == "complete"
    calls = sum(r["cost_spent_system"] > 0 for r in rows) + sum(r["cost_spent_judge"] > 0 for r in rows)
    assert len(store.ledger_rows(run.run_id)) == calls


def test_cached_run_needs_no_key(write_experiment, git_lab, store):
    p = write_experiment("sweep", LLM_EXP)
    cached = NeedsKey(all_cached=True)
    out = go(p, git_lab, store, system=cached)
    assert all(r.status == "complete" for r in out.records)
    p2 = write_experiment("sweep2", LLM_EXP.replace("name: sweep", "name: sweep2").replace("[0.4, 0.9]", "[0.5]"))
    with pytest.raises(RunRefused, match="ANTHROPIC_API_KEY"):
        go(p2, git_lab, store, system=NeedsKey())


def test_cli_dry_run_prints_estimate(write_experiment, git_lab, monkeypatch):
    from evallab.cli import app

    p = write_experiment("sweep", LLM_EXP)
    monkeypatch.chdir(git_lab.root)
    r = CliRunner().invoke(app, ["run", str(p), "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "quality=0.4" in r.output and "remaining $1.00" in r.output
    assert Store(git_lab.store_path).list_runs() == []


def test_cli_budget(git_lab, monkeypatch):
    from evallab.cli import app

    monkeypatch.chdir(git_lab.root)
    r = CliRunner().invoke(app, ["budget"])
    assert r.exit_code == 0 and "spent $0.00 of $1.00" in r.output


def test_shared_config_is_reused_across_experiments(write_experiment, git_lab, store):
    first = go(write_experiment("free", FREE_EXP), git_lab, store)
    other = write_experiment("other", FREE_EXP.replace("name: free", "name: other").replace("[0.4, 0.9]", "[0.9, 0.95]"))
    out = go(other, git_lab, store)
    assert len(out.records) == 1                               # quality=0.9 already ran under "free"
    shared = first.records[1].run_id
    assert store.find_run("other", "quality=0.9").run_id == shared
    assert {r.run_id for r in store.list_runs("other")} == {shared, out.records[0].run_id}
