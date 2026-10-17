"""Results store → JSON files for the static dashboard (dashboard/public/data)."""
import datetime as dt
import json
import re
from dataclasses import asdict
from pathlib import Path

import yaml

from evallab.config import Settings
from evallab.datasets import DatasetError, list_datasets, load_dataset
from evallab.store import Store

MANAGED = ("experiments", "runs", "datasets")
STATUS_RANK = {"complete": 0, "degraded": 1, "partial": 2, "running": 2}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return path


def export_all(store: Store, settings: Settings, out_dir: Path) -> list[Path]:
    out_dir = Path(out_dir)
    written: list[Path] = []
    questions: dict[str, dict[str, str]] = {}

    def question_map(ref: str) -> dict[str, str]:
        if ref not in questions:
            try:
                questions[ref] = {c.id: c.question for c in load_dataset(ref, settings).cases}
            except DatasetError:
                questions[ref] = {}
        return questions[ref]

    experiments = []
    for exp in store.list_experiments():
        spec = yaml.safe_load(exp["yaml"]) or {}
        labels = store.labels(exp["name"])
        runs = store.list_runs(exp["name"])
        run_views = [{**{k: v for k, v in asdict(r).items()}, "label": labels.get(r.run_id, r.label)} for r in runs]
        accuracies = [r.summary["accuracy"] for r in runs if r.summary and r.summary.get("accuracy") is not None]
        slug = slugify(exp["name"])
        experiments.append({
            "name": exp["name"], "slug": slug, "description": spec.get("description", ""),
            "hypothesis": exp["hypothesis"], "llm": bool(spec.get("llm")), "runs": [r.run_id for r in runs],
            "status": max((r.status for r in runs), key=lambda s: STATUS_RANK.get(s, 3), default="empty"),
            "best_accuracy": max(accuracies) if accuracies else None,
            "spent": sum((r.summary or {}).get("cost_spent", 0.0) for r in runs),
        })
        written.append(_write(out_dir / "experiments" / f"{slug}.json", {
            "name": exp["name"], "slug": slug, "yaml": exp["yaml"], "git_sha": exp["git_sha"],
            "hypothesis": exp["hypothesis"], "description": spec.get("description", ""),
            "llm": bool(spec.get("llm")), "gate": spec.get("gate"), "runs": run_views,
        }))

    for run in store.list_runs():
        qs = question_map(run.dataset)
        cases = [{**row, "question": qs.get(row["case_id"])} for row in store.case_rows(run.run_id)]
        written.append(_write(out_dir / "runs" / f"{run.run_id}.json", {"run": asdict(run), "cases": cases}))

    for manifest in list_datasets(settings):
        versions = {}
        for v in manifest["versions"]:
            try:
                versions[v["version"]] = [c.model_dump() for c in load_dataset(f"{manifest['name']}@{v['version']}", settings).cases]
            except DatasetError:
                versions[v["version"]] = []
        written.append(_write(out_dir / "datasets" / f"{slugify(manifest['name'])}.json",
                              {"name": manifest["name"], "manifest": manifest, "versions": versions}))

    written.append(_write(out_dir / "index.json", {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "budget": {"total": settings.budget_total_usd, "spent": store.spent_total()},
        "experiments": experiments,
        "datasets": [m["name"] for m in list_datasets(settings)],
    }))

    keep = {p.resolve() for p in written}
    for sub in MANAGED:
        for p in (out_dir / sub).glob("*.json") if (out_dir / sub).exists() else []:
            if p.resolve() not in keep:
                p.unlink()
    return written
