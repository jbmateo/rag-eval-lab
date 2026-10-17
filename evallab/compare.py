"""Case-level regression report between two runs, with paired statistics and a gate.

Inputs are plain dicts (a run: run_id, experiment, label, status, config, system_version, dataset,
judge_model, summary; case rows as stored, optionally with "question"). dashboard/lib/compare.ts
ports this function and must produce identical JSON — keep every arithmetic step in the same order.
"""
from evallab.experiments import GateSpec
from evallab.stats import fsum_ltr, mcnemar_exact, mde_paired, paired_bootstrap_ci, verdict

STATUS_ORDER = ["regressed", "improved", "stable_fail", "stable_pass", "not_comparable"]
INCOMPLETE = ("partial", "running", "degraded")
OTHER_METRICS = ["hit@k", "evidence_recall@k", "answer_rate", "abstention_precision", "abstention_recall",
                 "citation_validity", "latency_p50_ms", "latency_p95_ms"]


def _mean(values: list[float]) -> float | None:
    return fsum_ltr(values) / len(values) if values else None


def _reason(b: dict, c: dict, answerable: bool) -> str | None:
    bm, cm = b["metrics"], c["metrics"]
    if bm.get("hit") is not None and cm.get("hit") is not None and bm["hit"] != cm["hit"]:
        return "retrieval_gained" if cm["hit"] else "retrieval_lost"
    if bm.get("abstained") is not None and cm.get("abstained") is not None and bm["abstained"] != cm["abstained"]:
        if answerable:
            return "wrongly_abstained" if cm["abstained"] else "stopped_abstaining"
        return "correctly_abstained" if cm["abstained"] else "hallucinated"
    bj, cj = b.get("judge"), c.get("judge")
    if bj and cj:
        if bj["correct"] != cj["correct"]:
            return "judge_correct" if cj["correct"] else "judge_incorrect"
        if bj["unsupported_claims"] != cj["unsupported_claims"]:
            return "unsupported_claims"
    return None


def _snapshot(row: dict | None) -> dict | None:
    if row is None:
        return None
    trace = row.get("trace") or {}
    return {"status": row["status"], "pass": row["pass"], "answer_status": trace.get("status"),
            "sentences": trace.get("sentences", []), "judge": row.get("judge"), "error": row.get("error")}


def _metric(base_vals: list[float], cand_vals: list[float], higher_is_better: bool = True) -> dict:
    delta, lo, hi = paired_bootstrap_ci(base_vals, cand_vals)
    return {"n": len(base_vals), "base": _mean(base_vals), "cand": _mean(cand_vals), "delta": delta,
            "lo": lo, "hi": hi, "verdict": verdict(lo, hi, higher_is_better)}


def _run_view(run: dict) -> dict:
    return {k: run.get(k) for k in ("run_id", "experiment", "label", "status")}


def compare_runs(base: dict, base_rows: list[dict], cand: dict, cand_rows: list[dict],
                 allow_incomplete: bool = False) -> dict:
    warnings: list[str] = []
    for role, run in (("baseline", base), ("candidate", cand)):
        if run["status"] in INCOMPLETE:
            if not allow_incomplete:
                raise ValueError(f"The {role} run {run['run_id']} is {run['status']}; pass --allow-incomplete to compare anyway")
            warnings.append(f"{role} run is {run['status']}")

    b_by, c_by = {r["case_id"]: r for r in base_rows}, {r["case_id"]: r for r in cand_rows}
    ids = sorted(set(b_by) | set(c_by))
    shared = [i for i in ids if i in b_by and i in c_by]
    if base["dataset"] != cand["dataset"]:
        warnings.insert(0, f"datasets differ ({base['dataset']} vs {cand['dataset']}): comparing {len(shared)} shared cases")

    cases, pairs = [], []
    for cid in ids:
        b, c = b_by.get(cid), c_by.get(cid)
        ref = b or c
        entry = {"case_id": cid, "tag": ref["tag"], "answerable": ref["answerable"], "question": ref.get("question"),
                 "status": "not_comparable", "reason": None, "base": _snapshot(b), "cand": _snapshot(c)}
        ok = b is not None and c is not None and b["status"] == "ok" and c["status"] == "ok"
        if ok and b["pass"] is not None and c["pass"] is not None:
            pairs.append((b, c))
            if b["pass"] and c["pass"]:
                entry["status"] = "stable_pass"
            elif not b["pass"] and not c["pass"]:
                entry["status"] = "stable_fail"
            else:
                entry["status"] = "improved" if c["pass"] else "regressed"
                entry["reason"] = _reason(b, c, ref["answerable"])
        elif ok and b["pass"] is None and c["pass"] is None:
            continue  # not scored in either run (e.g. unanswerable cases in a retrieval-only run)
        cases.append(entry)
    cases.sort(key=lambda e: (STATUS_ORDER.index(e["status"]), e["case_id"]))

    counts = {s: sum(1 for e in cases if e["status"] == s) for s in
              ["improved", "regressed", "stable_pass", "stable_fail", "not_comparable"]}
    rr = [(b, c) for b, c in pairs if b["metrics"].get("rr") is not None and c["metrics"].get("rr") is not None]
    lat = [(b, c) for b, c in pairs if not b["cached"] and not c["cached"]
           and b["latency_ms"] is not None and c["latency_ms"] is not None]
    summary = {
        "accuracy": _metric([float(b["pass"]) for b, _ in pairs], [float(c["pass"]) for _, c in pairs]),
        "mrr": _metric([b["metrics"]["rr"] for b, _ in rr], [c["metrics"]["rr"] for _, c in rr]),
        "latency_ms": _metric([float(b["latency_ms"]) for b, _ in lat], [float(c["latency_ms"]) for _, c in lat],
                              higher_is_better=False),
        "cost_per_case": _metric([b["cost_nominal_system"] for b, _ in pairs], [c["cost_nominal_system"] for _, c in pairs],
                                 higher_is_better=False),
    }
    by_tag = {}
    for tag in sorted({b["tag"] for b, _ in pairs}):
        tp = [(b, c) for b, c in pairs if b["tag"] == tag]
        by_tag[tag] = {"n": len(tp),
                       "improved": sum(1 for b, c in tp if not b["pass"] and c["pass"]),
                       "regressed": sum(1 for b, c in tp if b["pass"] and not c["pass"]),
                       "base_accuracy": _mean([float(b["pass"]) for b, _ in tp]),
                       "cand_accuracy": _mean([float(c["pass"]) for _, c in tp])}
    keys = sorted(set(base["config"]) | set(cand["config"]))
    bs, cs = base.get("summary") or {}, cand.get("summary") or {}
    return {
        "base": _run_view(base), "cand": _run_view(cand),
        "config_diff": {k: [base["config"].get(k), cand["config"].get(k)] for k in keys
                        if base["config"].get(k) != cand["config"].get(k)},
        "versions": {role: {k: run.get(k) for k in ("system_version", "dataset", "judge_model")}
                     for role, run in (("base", base), ("cand", cand))},
        "warnings": warnings,
        "n_compared": len(pairs),
        "summary": summary,
        "other": {m: {"base": bs.get(m), "cand": cs.get(m)} for m in OTHER_METRICS},
        "mcnemar_p": mcnemar_exact(counts["improved"], counts["regressed"]),
        "mde": mde_paired(len(pairs), counts["improved"] + counts["regressed"]),
        "counts": counts,
        "by_tag": by_tag,
        "cases": cases,
    }


def check_gate(report: dict, gate: GateSpec) -> list[str]:
    fails = []
    n_reg = report["counts"]["regressed"]
    if gate.max_regressed is not None and n_reg > gate.max_regressed:
        fails.append(f"regressed {n_reg} > {gate.max_regressed}")
    delta = report["summary"]["accuracy"]["delta"]
    if gate.min_accuracy_delta is not None and delta is not None and delta < gate.min_accuracy_delta:
        fails.append(f"accuracy delta {delta:+.3f} < {gate.min_accuracy_delta:+.3f}")
    cost = report["summary"]["cost_per_case"]
    if gate.max_cost_ratio is not None and cost["base"] and cost["cand"] is not None:
        ratio = cost["cand"] / cost["base"]
        if ratio > gate.max_cost_ratio:
            fails.append(f"cost per case ratio {ratio:.2f} > {gate.max_cost_ratio:.2f}")
    return fails


# --- Markdown ---------------------------------------------------------------------------------------


def _f(v, digits: int = 3) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def _pct(v) -> str:
    return "—" if v is None else f"{v * 100:+.1f} pts"


def render_markdown(r: dict) -> str:
    b, c = r["base"], r["cand"]
    out = [f"# Compare: {b['experiment']}:{b['label']} → {c['experiment']}:{c['label']}", "",
           f"Baseline `{b['run_id']}` ({b['status']}) · Candidate `{c['run_id']}` ({c['status']})", ""]
    for w in r["warnings"]:
        out.append(f"> ⚠ {w}")
    if r["warnings"]:
        out.append("")
    out += ["## What changed", "", "| setting | baseline | candidate |", "|---|---|---|"]
    out += [f"| {k} | {_f(v[0])} | {_f(v[1])} |" for k, v in r["config_diff"].items()] or ["| (none) | | |"]
    vb, vc = r["versions"]["base"], r["versions"]["cand"]
    out += ["", f"System {vb['system_version']} → {vc['system_version']} · dataset {vb['dataset']} → {vc['dataset']} · "
                f"judge {vb['judge_model']} → {vc['judge_model']}", ""]
    out += ["## Summary", "", f"{r['n_compared']} paired cases · McNemar p = {_f(r['mcnemar_p'])} · "
                              f"minimum detectable change ≈ {_pct(r['mde'])}", "",
            "| metric | baseline | candidate | Δ | 95% CI | verdict |", "|---|---|---|---|---|---|"]
    for name, m in r["summary"].items():
        ci = "—" if m["lo"] is None else f"[{_f(m['lo'], 4)}, {_f(m['hi'], 4)}]"
        out.append(f"| {name} | {_f(m['base'], 4)} | {_f(m['cand'], 4)} | {_f(m['delta'], 4)} | {ci} | {m['verdict']} |")
    for name, m in r["other"].items():
        out.append(f"| {name} | {_f(m['base'], 4)} | {_f(m['cand'], 4)} | | | |")
    counts = r["counts"]
    out += ["", "## Cases", "", " · ".join(f"{k.replace('_', ' ')}: {v}" for k, v in counts.items()), "",
            "| tag | n | improved | regressed | baseline acc | candidate acc |", "|---|---|---|---|---|---|"]
    out += [f"| {t} | {v['n']} | {v['improved']} | {v['regressed']} | {_f(v['base_accuracy'])} | {_f(v['cand_accuracy'])} |"
            for t, v in r["by_tag"].items()]
    for status, title in (("regressed", "▼ Regressed"), ("improved", "▲ Improved")):
        group = [e for e in r["cases"] if e["status"] == status]
        if not group:
            continue
        out += ["", f"### {title} ({len(group)})", ""]
        for e in group:
            out.append(f"- **{e['case_id']}** [{e['tag']}] {e['question'] or ''} — reason: `{e['reason'] or 'unclear'}`")
            for role, snap in (("baseline", e["base"]), ("candidate", e["cand"])):
                answer = " ".join(snap["sentences"]) or f"({snap['answer_status'] or 'no answer'})"
                judge = snap["judge"]["reason"] if snap["judge"] else "—"
                out.append(f"  - {role}: {answer} · judge: {judge}")
    fails = [e["case_id"] for e in r["cases"] if e["status"] == "stable_fail"]
    if fails:
        out += ["", f"<details><summary>Stable fail ({len(fails)})</summary>", "", ", ".join(fails), "", "</details>"]
    return "\n".join(out) + "\n"
