"""SQLite results store: experiments, runs, per-case results and the spend ledger."""
import datetime as dt
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
  name TEXT PRIMARY KEY, yaml TEXT NOT NULL, git_sha TEXT NOT NULL, hypothesis TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, experiment TEXT NOT NULL, label TEXT NOT NULL, config_json TEXT NOT NULL,
  system TEXT NOT NULL, system_version TEXT NOT NULL, dataset TEXT NOT NULL, dataset_sha TEXT NOT NULL,
  subset TEXT, judge_model TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL,
  finished_at TEXT, summary_json TEXT);
CREATE TABLE IF NOT EXISTS case_results (
  run_id TEXT NOT NULL, case_id TEXT NOT NULL, tag TEXT NOT NULL, answerable INTEGER NOT NULL,
  status TEXT NOT NULL, pass INTEGER, metrics_json TEXT NOT NULL, trace_json TEXT, judge_json TEXT,
  error TEXT, latency_ms INTEGER, cached INTEGER NOT NULL,
  cost_spent_system REAL NOT NULL, cost_spent_judge REAL NOT NULL,
  cost_nominal_system REAL NOT NULL, cost_nominal_judge REAL NOT NULL,
  PRIMARY KEY (run_id, case_id));
CREATE TABLE IF NOT EXISTS ledger (
  ts TEXT NOT NULL, run_id TEXT NOT NULL, case_id TEXT NOT NULL, model TEXT NOT NULL, role TEXT NOT NULL,
  usd REAL NOT NULL);
"""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RunRecord:
    run_id: str
    experiment: str
    label: str
    config: dict
    system: str
    system_version: str
    dataset: str
    dataset_sha: str
    subset: str | None
    judge_model: str
    status: str
    started_at: str
    finished_at: str | None = None
    summary: dict | None = field(default=None)


def _bool(v):
    return None if v is None else bool(v)


class Store:
    def __init__(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # experiments
    def upsert_experiment(self, name: str, yaml_text: str, git_sha: str, hypothesis: str | None) -> None:
        self.conn.execute(
            "INSERT INTO experiments VALUES (?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET "
            "yaml=excluded.yaml, git_sha=excluded.git_sha, hypothesis=excluded.hypothesis",
            (name, yaml_text, git_sha, hypothesis, now()))
        self.conn.commit()

    def get_experiment(self, name: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM experiments WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    def list_experiments(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM experiments ORDER BY name")]

    # runs
    def create_run(self, r: RunRecord) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r.run_id, r.experiment, r.label, json.dumps(r.config, sort_keys=True), r.system, r.system_version,
             r.dataset, r.dataset_sha, r.subset, r.judge_model, r.status, r.started_at, r.finished_at,
             json.dumps(r.summary) if r.summary is not None else None))
        self.conn.commit()

    @staticmethod
    def _run(row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"], experiment=row["experiment"], label=row["label"],
            config=json.loads(row["config_json"]), system=row["system"], system_version=row["system_version"],
            dataset=row["dataset"], dataset_sha=row["dataset_sha"], subset=row["subset"],
            judge_model=row["judge_model"], status=row["status"], started_at=row["started_at"],
            finished_at=row["finished_at"],
            summary=json.loads(row["summary_json"]) if row["summary_json"] else None)

    def get_run(self, run_id_or_prefix: str) -> RunRecord:
        rows = self.conn.execute("SELECT * FROM runs WHERE run_id LIKE ? ORDER BY run_id",
                                 (run_id_or_prefix + "%",)).fetchall()
        if not rows:
            raise KeyError(f"No run matches {run_id_or_prefix!r}")
        if len(rows) > 1:
            raise ValueError(f"Run prefix {run_id_or_prefix!r} is ambiguous: {', '.join(r['run_id'] for r in rows)}")
        return self._run(rows[0])

    def find_run(self, experiment: str, label: str) -> RunRecord | None:
        row = self.conn.execute("SELECT * FROM runs WHERE experiment=? AND label=? ORDER BY started_at DESC LIMIT 1",
                                (experiment, label)).fetchone()
        return self._run(row) if row else None

    def list_runs(self, experiment: str | None = None) -> list[RunRecord]:
        if experiment is None:
            rows = self.conn.execute("SELECT * FROM runs ORDER BY started_at, run_id")
        else:
            rows = self.conn.execute("SELECT * FROM runs WHERE experiment=? ORDER BY started_at, run_id", (experiment,))
        return [self._run(r) for r in rows]

    def set_status(self, run_id: str, status: str) -> None:
        self.conn.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))
        self.conn.commit()

    def finish_run(self, run_id: str, status: str, summary: dict) -> None:
        self.conn.execute("UPDATE runs SET status=?, finished_at=?, summary_json=? WHERE run_id=?",
                          (status, now(), json.dumps(summary), run_id))
        self.conn.commit()

    # cases
    def put_case(self, run_id: str, row: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO case_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, row["case_id"], row["tag"], int(row["answerable"]), row["status"],
             None if row["pass"] is None else int(row["pass"]), json.dumps(row["metrics"]),
             json.dumps(row["trace"]) if row.get("trace") is not None else None,
             json.dumps(row["judge"]) if row.get("judge") is not None else None, row.get("error"),
             row["latency_ms"], int(row["cached"]), row["cost_spent_system"], row["cost_spent_judge"],
             row["cost_nominal_system"], row["cost_nominal_judge"]))
        self.conn.commit()

    def case_rows(self, run_id: str) -> list[dict]:
        out = []
        for r in self.conn.execute("SELECT * FROM case_results WHERE run_id=? ORDER BY case_id", (run_id,)):
            out.append({
                "case_id": r["case_id"], "tag": r["tag"], "answerable": bool(r["answerable"]), "status": r["status"],
                "pass": _bool(r["pass"]), "metrics": json.loads(r["metrics_json"]),
                "trace": json.loads(r["trace_json"]) if r["trace_json"] else None,
                "judge": json.loads(r["judge_json"]) if r["judge_json"] else None, "error": r["error"],
                "latency_ms": r["latency_ms"], "cached": bool(r["cached"]),
                "cost_spent_system": r["cost_spent_system"], "cost_spent_judge": r["cost_spent_judge"],
                "cost_nominal_system": r["cost_nominal_system"], "cost_nominal_judge": r["cost_nominal_judge"],
            })
        return out

    def done_case_ids(self, run_id: str) -> set[str]:
        return {r[0] for r in self.conn.execute("SELECT case_id FROM case_results WHERE run_id=?", (run_id,))}

    # ledger
    def add_ledger(self, run_id: str, case_id: str, model: str, role: str, usd: float) -> None:
        self.conn.execute("INSERT INTO ledger VALUES (?,?,?,?,?,?)", (now(), run_id, case_id, model, role, usd))
        self.conn.commit()

    def spent_total(self) -> float:
        return float(self.conn.execute("SELECT COALESCE(SUM(usd), 0) FROM ledger").fetchone()[0])

    def ledger_rows(self, run_id: str | None = None) -> list[dict]:
        q, args = ("SELECT * FROM ledger", ()) if run_id is None else ("SELECT * FROM ledger WHERE run_id=?", (run_id,))
        return [dict(r) for r in self.conn.execute(q, args)]
