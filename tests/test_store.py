import pytest

from evallab.store import RunRecord, Store


def rec(run_id="abc123def456", label="base", experiment="exp", started="2026-10-18T10:00:00Z"):
    return RunRecord(run_id=run_id, experiment=experiment, label=label, config={"k": 1}, system="fake",
                     system_version="fake@1", dataset="drones@v1", dataset_sha="s", subset=None,
                     judge_model="fake", status="running", started_at=started)


def case_row(case_id="q1", passed=True, **over):
    row = {"case_id": case_id, "tag": "t", "answerable": True, "status": "ok", "pass": passed,
           "metrics": {"hit": True}, "trace": {"status": "answered"}, "judge": {"correct": True},
           "error": None, "latency_ms": 12, "cached": False, "cost_spent_system": 0.001,
           "cost_spent_judge": 0.0005, "cost_nominal_system": 0.001, "cost_nominal_judge": 0.0005}
    return {**row, **over}


def test_roundtrip_run_and_cases(tmp_path):
    s = Store(tmp_path / "r.db")
    s.upsert_experiment("exp", "name: exp\n", "sha1", "H1")
    s.create_run(rec())
    s.put_case("abc123def456", case_row())
    s.put_case("abc123def456", case_row("q2", None, answerable=False))
    s.finish_run("abc123def456", "complete", {"accuracy": 1.0})
    r = s.get_run("abc123def456")
    assert r.status == "complete" and r.summary == {"accuracy": 1.0} and r.finished_at
    rows = s.case_rows("abc123def456")
    assert [x["case_id"] for x in rows] == ["q1", "q2"]
    assert rows[0] == case_row() and rows[1]["pass"] is None and rows[1]["answerable"] is False
    assert s.done_case_ids("abc123def456") == {"q1", "q2"}
    assert s.get_experiment("exp")["hypothesis"] == "H1"


def test_prefix_lookup_ambiguous(tmp_path):
    s = Store(tmp_path / "r.db")
    s.create_run(rec("abc111111111"))
    s.create_run(rec("abc222222222", label="other"))
    assert s.get_run("abc1").run_id == "abc111111111"
    with pytest.raises(ValueError, match="abc111111111"):
        s.get_run("abc")
    with pytest.raises(KeyError, match="zzz"):
        s.get_run("zzz")


def test_find_run_latest(tmp_path):
    s = Store(tmp_path / "r.db")
    s.create_run(rec("aaa000000001", started="2026-10-18T10:00:00Z"))
    s.create_run(rec("aaa000000002", started="2026-10-18T11:00:00Z"))
    s.link_run("exp", "base", "aaa000000001")
    s.link_run("exp", "base", "aaa000000002")
    assert s.find_run("exp", "base").run_id == "aaa000000002"
    assert s.find_run("exp", "nope") is None
    assert [r.run_id for r in s.list_runs("exp")] == ["aaa000000001", "aaa000000002"]


def test_put_case_is_upsert(tmp_path):
    s = Store(tmp_path / "r.db")
    s.create_run(rec())
    s.put_case("abc123def456", case_row(passed=False))
    s.put_case("abc123def456", case_row(passed=True))
    rows = s.case_rows("abc123def456")
    assert len(rows) == 1 and rows[0]["pass"] is True


def test_spent_total_sums_ledger(tmp_path):
    s = Store(tmp_path / "r.db")
    assert s.spent_total() == 0.0
    s.add_ledger("r1", "q1", "m", "system", 0.25)
    s.add_ledger("r1", "q1", "m", "judge", 0.05)
    assert abs(s.spent_total() - 0.30) < 1e-12


def test_reopen_persists(tmp_path):
    s = Store(tmp_path / "r.db")
    s.create_run(rec())
    s.close()
    assert Store(tmp_path / "r.db").get_run("abc").label == "base"
