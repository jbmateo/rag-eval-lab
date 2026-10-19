"""Judge reliability: sample judged cases for hand labelling, then score judge-vs-human agreement."""
import csv
import datetime as dt
from pathlib import Path

from evallab.config import Settings
from evallab.datasets import DatasetError, load_dataset
from evallab.stats import Mulberry32
from evallab.store import Store

FIELDS = ["run_id", "model", "case_id", "question", "answer", "evidence", "judge_correct", "judge_unsupported",
          "judge_reason", "human_correct", "human_unsupported"]
TRUE, FALSE = {"1", "true", "yes", "y"}, {"0", "false", "no", "n"}


def sample(store: Store, settings: Settings, run_ids: list[str], n: int = 30, seed: int = 0) -> Path:
    runs = [store.get_run(r) for r in run_ids]
    groups: dict[str, list[tuple]] = {}
    datasets = {}
    for run in runs:
        if run.dataset not in datasets:
            try:
                datasets[run.dataset] = {c.id: c for c in load_dataset(run.dataset, settings).cases}
            except DatasetError:
                datasets[run.dataset] = {}
        model = str(run.config.get("model", "?"))
        for row in store.case_rows(run.run_id):
            if row["judge"] is not None:
                groups.setdefault(model, []).append((run, row))
    models = sorted(groups)
    rng = Mulberry32(seed)
    picked = []
    for i, model in enumerate(models):
        share = n // len(models) + (1 if i < n % len(models) else 0)
        items = sorted(groups[model], key=lambda x: (x[0].run_id, x[1]["case_id"]))
        picked += [(model, *x) for x in rng.shuffle(items)[:share]]
    out = settings.root / "spotcheck" / f"{dt.date.today().isoformat()}-{'-'.join(r.run_id[:6] for r in runs)}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for model, run, row in picked:
            case = datasets[run.dataset].get(row["case_id"])
            w.writerow({
                "run_id": run.run_id, "model": model, "case_id": row["case_id"],
                "question": case.question if case else "",
                "answer": " ".join((row["trace"] or {}).get("sentences", [])),
                "evidence": (" | ".join(f"[{e.document}] {e.evidence}" for e in case.expected)
                             or "(none: the corpus does not answer this question)") if case else "",
                "judge_correct": str(row["judge"]["correct"]).lower(),
                "judge_unsupported": row["judge"]["unsupported_claims"], "judge_reason": row["judge"]["reason"],
                "human_correct": "", "human_unsupported": "",
            })
    return out


def _bool(v: str) -> bool | None:
    v = (v or "").strip().lower()
    return True if v in TRUE else False if v in FALSE else None


def _agreement(pairs: list[tuple[bool, bool]]) -> dict:
    n = len(pairs)
    if n == 0:
        return {"n": 0, "agreement": None, "kappa": None}
    po = sum(1 for j, h in pairs if j == h) / n
    pj, ph = sum(1 for j, _ in pairs if j) / n, sum(1 for _, h in pairs if h) / n
    pe = pj * ph + (1 - pj) * (1 - ph)
    return {"n": n, "agreement": po, "kappa": None if pe == 1 else (po - pe) / (1 - pe)}


def score(csv_path: Path) -> dict:
    by_model: dict[str, list] = {}
    pairs = []
    for row in csv.DictReader(Path(csv_path).open()):
        j, h = _bool(row["judge_correct"]), _bool(row["human_correct"])
        if j is None or h is None:
            continue
        pairs.append((j, h))
        by_model.setdefault(row["model"], []).append((j, h))
    return _agreement(pairs) | {"by_model": {m: _agreement(p) for m, p in sorted(by_model.items())}}
