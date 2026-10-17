import copy
import json

import pytest
from typer.testing import CliRunner

from evallab.compare import check_gate, compare_runs, render_markdown
from evallab.experiments import GateSpec
from tests.conftest import FIXTURES

PAIR = json.loads((FIXTURES / "compare_pair.json").read_text())


def report(pair=PAIR, **kw):
    p = copy.deepcopy(pair)
    return compare_runs(p["base"], p["base_rows"], p["cand"], p["cand_rows"], **kw)


def test_classification_and_reasons():
    r = report()
    got = {c["case_id"]: (c["status"], c["reason"]) for c in r["cases"]}
    assert got["a1"] == ("regressed", "retrieval_lost")
    assert got["a2"] == ("improved", "judge_correct")
    assert got["a3"] == ("regressed", "wrongly_abstained")
    assert got["a4"] == ("stable_pass", None)
    assert got["a5"] == ("stable_fail", None)
    assert got["u1"] == ("regressed", "hallucinated")
    assert got["u2"] == ("improved", "correctly_abstained")
    assert got["a6"][0] == "not_comparable" and got["n9"][0] == "not_comparable"
    assert got["a7"] == ("regressed", "unsupported_claims")
    assert got["a8"] == ("improved", "retrieval_gained")
    assert r["counts"] == {"improved": 3, "regressed": 4, "stable_pass": 1, "stable_fail": 1, "not_comparable": 2}
    order = [c["status"] for c in r["cases"]]
    assert order == sorted(order, key=["regressed", "improved", "stable_fail", "stable_pass", "not_comparable"].index)


def test_summary_and_stats():
    r = report()
    acc = r["summary"]["accuracy"]
    assert (acc["base"], acc["cand"]) == (5 / 9, 4 / 9) and acc["lo"] <= acc["delta"] <= acc["hi"]
    assert r["summary"]["cost_per_case"]["verdict"] == "worse"       # cost doubled on every case
    assert r["n_compared"] == 9 and 0 < r["mcnemar_p"] <= 1 and r["mde"] > 0
    assert r["config_diff"] == {"quality": [0.4, 0.9]}
    assert r["by_tag"]["unanswerable"] == {"n": 2, "improved": 1, "regressed": 1, "base_accuracy": 0.5, "cand_accuracy": 0.5}


def test_report_matches_fixture():
    expected = json.loads((FIXTURES / "compare_expected.json").read_text())
    assert json.loads(json.dumps(report())) == expected


def test_dataset_mismatch_warns_and_uses_shared():
    p = copy.deepcopy(PAIR)
    p["cand"]["dataset"] = "drones@v2"
    r = report(p)
    assert any(w.startswith("datasets differ (drones@v1 vs drones@v2): comparing 10 shared cases") for w in r["warnings"])


def test_gate_failures():
    r = report()
    fails = check_gate(r, GateSpec(max_regressed=0, min_accuracy_delta=0.0, max_cost_ratio=1.2))
    assert "regressed 4 + errored 1 > 0" in fails[0] and len(fails) == 3   # review #5: a6 passed, then errored
    assert check_gate(r, GateSpec()) == []


def test_incomplete_run_refused():
    p = copy.deepcopy(PAIR)
    p["cand"]["status"] = "partial"
    with pytest.raises(ValueError, match="--allow-incomplete"):
        report(p)
    assert "candidate run is partial" in report(p, allow_incomplete=True)["warnings"]


def test_markdown_renders_none_as_dash():
    p = copy.deepcopy(PAIR)
    for rows in (p["base_rows"], p["cand_rows"]):
        for row in rows:
            row["pass"] = None if not row["answerable"] else row["pass"]
            row["latency_ms"] = None
    p["base"]["summary"] = p["cand"]["summary"] = {"answer_rate": None}
    md = render_markdown(report(p))
    assert "—" in md and "nan" not in md.lower() and "None" not in md
    assert "Regressed" in md and "a1" in md


def test_cli_compare_and_gate(git_lab, write_experiment, monkeypatch):
    from evallab.cli import app

    write_experiment("sweep", "name: sweep\nsystem: fake\ndataset: drones@v1\nllm: true\njudge: true\n"
                              "hypothesis: h\ngrid: {quality: [0.9, 0.2]}\ngate: {max_regressed: 0}\n")
    monkeypatch.chdir(git_lab.root)
    runner = CliRunner()
    assert runner.invoke(app, ["run", "experiments/sweep.yaml", "--yes"]).exit_code == 0
    r = runner.invoke(app, ["compare", "sweep:quality=0.9", "sweep:quality=0.2", "--format", "json"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["counts"]["regressed"] > 0
    g = runner.invoke(app, ["compare", "sweep:quality=0.9", "sweep:quality=0.2", "--gate"])
    assert g.exit_code == 1 and "regressed" in g.output
    ok = runner.invoke(app, ["compare", "sweep:quality=0.9", "sweep:quality=0.2", "--gate", "--max-regressed", "99"])
    assert ok.exit_code == 0


def test_gate_fails_with_nothing_to_compare():
    """Review #5: a gate over zero paired cases must not pass vacuously."""
    p = copy.deepcopy(PAIR)
    for row in p["cand_rows"]:
        row["status"], row["pass"] = "error", None
    r = report(p)
    assert r["n_compared"] == 0
    assert any("no paired cases" in f for f in check_gate(r, GateSpec(max_regressed=0)))


def test_errored_after_pass_counted():
    assert report()["errored_after_pass"] == 1
