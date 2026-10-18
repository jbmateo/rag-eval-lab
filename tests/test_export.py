import json

from evallab.export import export_all, slugify
from evallab.runner import run_experiment
from evallab.store import Store
from tests.test_runner import FREE_EXP, LLM_EXP, PRICING


def _populate(git_lab, write_experiment, name="sweep", text=LLM_EXP):
    store = Store(git_lab.store_path)
    run_experiment(write_experiment(name, text), git_lab, store, pricing=PRICING, yes=True, echo=lambda *_: None)
    return store


def test_export_files_and_shapes(git_lab, write_experiment):
    store = _populate(git_lab, write_experiment)
    out = git_lab.export_dir
    files = export_all(store, git_lab, out)
    index = json.loads((out / "index.json").read_text())
    assert index["budget"] == {"total": 1.0, "spent": store.spent_total()}
    exp = index["experiments"][0]
    assert exp["name"] == "sweep" and exp["slug"] == "sweep" and len(exp["runs"]) == 2
    assert exp["status"] == "complete" and exp["hypothesis"] and exp["best_accuracy"] is not None
    detail = json.loads((out / "experiments/sweep.json").read_text())
    assert [r["label"] for r in detail["runs"]] == ["quality=0.4", "quality=0.9"]
    assert detail["yaml"].startswith("name: sweep") and detail["runs"][0]["summary"]["accuracy_ci"]
    run = json.loads((out / f"runs/{exp['runs'][0]}.json").read_text())
    assert run["run"]["run_id"] == exp["runs"][0] and len(run["cases"]) == 20
    assert run["cases"][0]["question"] and run["cases"][0]["trace"]["retrieved"]
    ds = json.loads((out / "datasets/drones.json").read_text())
    assert len(ds["versions"]["v1"]) == 20 and ds["manifest"]["name"] == "drones"
    assert all(p.exists() for p in files)


def test_shared_run_listed_under_both_experiments(git_lab, write_experiment):
    store = _populate(git_lab, write_experiment, "free", FREE_EXP)
    run_experiment(write_experiment("other", FREE_EXP.replace("name: free", "name: other")), git_lab, store,
                   pricing=PRICING, yes=True, echo=lambda *_: None)
    export_all(store, git_lab, git_lab.export_dir)
    index = json.loads((git_lab.export_dir / "index.json").read_text())
    runs = {e["name"]: set(e["runs"]) for e in index["experiments"]}
    assert runs["free"] == runs["other"] and len(runs["free"]) == 2


def test_slugified_names():
    assert slugify("My Sweep/2") == "my-sweep-2" and slugify("rq1-retrieval") == "rq1-retrieval"


def test_stale_files_removed(git_lab, write_experiment):
    store = _populate(git_lab, write_experiment)
    stale = git_lab.export_dir / "runs" / "deadbeef0000.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("{}")
    export_all(store, git_lab, git_lab.export_dir)
    assert not stale.exists()


def test_findings_exported_when_present(git_lab, write_experiment):
    store = _populate(git_lab, write_experiment)
    (git_lab.root / "findings.yaml").write_text("- id: H1\n  experiment: sweep\n  verdict: holds\n")
    export_all(store, git_lab, git_lab.export_dir)
    index = json.loads((git_lab.export_dir / "index.json").read_text())
    assert index["findings"] == [{"id": "H1", "experiment": "sweep", "verdict": "holds"}]


def test_findings_empty_when_absent(git_lab, write_experiment):
    store = _populate(git_lab, write_experiment)
    export_all(store, git_lab, git_lab.export_dir)
    assert json.loads((git_lab.export_dir / "index.json").read_text())["findings"] == []
