import csv
import math
import shutil

from evallab.runner import run_experiment
from evallab.spotcheck import FIELDS, sample, score
from evallab.store import Store
from tests.conftest import FIXTURES, git
from tests.test_runner import PRICING

EXP = """name: models
system: fake
dataset: drones@v1
llm: true
judge: true
hypothesis: h
grid: {model: [fake-model, fake-model-b], quality: [1.0]}
"""


def _runs(git_lab, write_experiment):
    import yaml

    prices = yaml.safe_load((git_lab.root / "pricing.yaml").read_text())
    prices["models"]["fake-model-b"] = {"input": 1.0, "output": 1.0}
    (git_lab.root / "pricing.yaml").write_text(yaml.safe_dump(prices))
    from evallab import pricing

    store = Store(git_lab.store_path)
    out = run_experiment(write_experiment("models", EXP), git_lab, store, pricing=pricing.load(git_lab.root / "pricing.yaml"),
                         yes=True, echo=lambda *_: None)
    return store, [r.run_id for r in out.records]


def test_sample_is_stratified(git_lab, write_experiment):
    store, run_ids = _runs(git_lab, write_experiment)
    path = sample(store, git_lab, run_ids, n=10, seed=0)
    rows = list(csv.DictReader(path.open()))
    assert list(rows[0]) == FIELDS and len(rows) == 10
    assert sorted(r["model"] for r in rows) == ["fake-model"] * 5 + ["fake-model-b"] * 5
    assert all(r["question"] and r["evidence"] and r["human_correct"] == "" for r in rows)
    again = sample(store, git_lab, run_ids, n=10, seed=0)
    assert [r["case_id"] for r in csv.DictReader(again.open())] == [r["case_id"] for r in rows]


def _write(path, table):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for (judge, human, model), count in table.items():
            for _ in range(count):
                w.writerow({k: "" for k in FIELDS} | {"model": model, "judge_correct": judge, "human_correct": human})


def test_kappa_known(tmp_path):
    p = tmp_path / "s.csv"
    _write(p, {("true", "yes", "a"): 10, ("true", "no", "a"): 2, ("false", "yes", "b"): 3, ("false", "no", "b"): 15})
    s = score(p)
    assert s["n"] == 30 and math.isclose(s["agreement"], 25 / 30)
    assert math.isclose(s["kappa"], 0.6575342465753424)
    assert s["by_model"]["a"]["n"] == 12 and s["by_model"]["b"]["agreement"] == 15 / 18


def test_unlabelled_rows_skipped(tmp_path):
    p = tmp_path / "s.csv"
    _write(p, {("true", "1", "a"): 2, ("true", "", "a"): 5})
    s = score(p)
    assert s["n"] == 2 and s["kappa"] is None   # all agree on one class: kappa undefined
