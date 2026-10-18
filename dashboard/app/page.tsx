import Link from "next/link";
import { ChunkCharts, ModelCharts, Panel, RetrievalModes, SpendBars, ThresholdChart } from "@/components/OverviewCharts";
import { getDataset, getExperiment, getIndex } from "@/lib/data";
import { pct, usd } from "@/lib/format";
import { chunkSeries, modelComparison, retrievalByTag, spendByExperiment, sweepGrid, thresholdCurve, verdictCounts } from "@/lib/overview";
import type { ExperimentFile, Finding } from "@/lib/types";

const STEPS = ["--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5", "--seq-6", "--seq-7"];

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="text-sm text-ink-2">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
      {sub && <div className="mt-1 text-sm text-muted">{sub}</div>}
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const held = verdict.startsWith("holds");
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap text-sm font-medium ${held ? "text-good" : "text-critical"}`}>
      <span aria-hidden>{held ? "✓" : "✗"}</span>{verdict.charAt(0).toUpperCase() + verdict.slice(1)}
    </span>
  );
}

function compareHref(f: Finding, exps: Map<string, ExperimentFile>): string | null {
  const exp = exps.get(f.experiment);
  if (!exp || !f.compare) return null;
  const id = (label: string) => exp.runs.find((r) => r.label === label)?.run_id;
  const [b, c] = [id(f.compare[0]), id(f.compare[1])];
  return b && c ? `/compare/?base=${b}&cand=${c}&exp=${exp.slug}` : null;
}

export default async function Overview() {
  const index = await getIndex();
  const files = (await Promise.all(index.experiments.map((e) => getExperiment(e.slug)))).filter(Boolean) as ExperimentFile[];
  const exps = new Map(files.map((e) => [e.name, e]));
  const findings = index.findings ?? [];
  const { held, rejected } = verdictCounts(findings);
  const dataset = index.datasets[0] ? await getDataset(index.datasets[0]) : null;
  const latest = dataset?.manifest.versions.at(-1);
  const grid = sweepGrid(exps.get("retrieval-sweep"));
  const runs = new Set(files.flatMap((e) => e.runs.map((r) => r.run_id))).size;

  return (
    <div className="space-y-8">
      <section className="max-w-3xl space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="text-ink-2">
          Hypotheses about RAG Studio, each stated before it ran and tested case by case on a versioned dataset.
          Charts summarise every experiment; follow a hypothesis to see exactly which questions moved.
        </p>
      </section>

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4" aria-label="Headline numbers">
        <Tile label="API spend" value={`${usd(index.budget.spent, 2)} of ${usd(index.budget.total, 2)}`}
          sub={`${pct(index.budget.total ? index.budget.spent / index.budget.total : null, 0)} of the budget`} />
        <Tile label="Hypotheses" value={`${held} held · ${rejected} rejected`} sub={`${findings.length} tested`} />
        <Tile label="Experiments" value={String(index.experiments.length)} sub={`${runs} distinct runs`} />
        <Tile label="Dataset" value={dataset ? `${dataset.name}@${latest?.version}` : "—"}
          sub={latest ? `${latest.cases} questions` : undefined} />
      </section>

      {findings.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Hypothesis scoreboard</h2>
          <div className="relative overflow-x-auto rounded-lg border border-line bg-surface">
            <table className="w-full text-sm">
              <thead className="text-left text-muted">
                <tr className="border-b border-line">
                  <th className="px-3 py-2 font-medium">id</th><th className="px-3 py-2 font-medium">question</th>
                  <th className="px-3 py-2 font-medium">verdict</th><th className="px-3 py-2 font-medium">deciding number</th>
                  <th className="px-3 py-2 font-medium"><span className="sr-only">Links</span></th>
                </tr>
              </thead>
              <tbody>
                {findings.map((f) => {
                  const href = compareHref(f, exps);
                  const slug = exps.get(f.experiment)?.slug;
                  return (
                    <tr key={f.id} className="border-b border-line align-top last:border-0">
                      <td className="whitespace-nowrap px-3 py-2 font-semibold">{f.id}</td>
                      <td className="min-w-48 px-3 py-2">{f.question}</td>
                      <td className="px-3 py-2"><VerdictBadge verdict={f.verdict} /></td>
                      <td className="num min-w-48 px-3 py-2 text-ink-2">{f.evidence}</td>
                      <td className="whitespace-nowrap px-3 py-2">
                        {href && <Link href={href} className="text-series-1 hover:underline">Compare</Link>}
                        {slug && <> · <Link href={`/experiments/${slug}/`} className="text-series-1 hover:underline">Runs</Link></>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="grid gap-6 lg:grid-cols-2">
        {exps.has("model-sweep") && <ModelCharts data={modelComparison(exps.get("model-sweep"))} />}
        {(exps.has("gate-sweep") || exps.has("gate-sweep-high")) &&
          <ThresholdChart data={thresholdCurve(exps.get("gate-sweep"), exps.get("gate-sweep-high"))} />}
        {exps.has("chunk-sweep") && <ChunkCharts data={chunkSeries(exps.get("chunk-sweep"))} />}
        {exps.has("rq1-retrieval") && <RetrievalModes data={retrievalByTag(exps.get("rq1-retrieval"))} />}
        {grid.chunks.length > 0 && (
          <Panel title="Retrieval sweep: hit@k by chunk size and top_k"
            note="Hybrid retrieval, no LLM. Darker is higher; more chunks per question finds the evidence more often."
            table={{ head: ["chunk_chars", ...grid.topKs.map((k) => `top_k ${k}`)],
              rows: grid.chunks.map((c) => [c, ...grid.topKs.map((k) => pct(grid.value(c, k)))]) }}>
            <div className="overflow-x-auto">
              <table className="num w-full border-separate text-sm" style={{ borderSpacing: 2 }}>
                <thead><tr><th className="px-2 py-1 text-left font-medium text-muted">chunk_chars</th>
                  {grid.topKs.map((k) => <th key={k} className="px-2 py-1 text-left font-medium text-muted">top_k {k}</th>)}</tr></thead>
                <tbody>{grid.chunks.map((c) => (
                  <tr key={c}><th className="px-2 py-1 text-left font-medium">{c}</th>
                    {grid.topKs.map((k) => {
                      const v = grid.value(c, k);
                      // Values sit between ~85% and 100%, so the ramp spans that range to stay readable.
                      const i = v === null ? -1 : Math.max(0, Math.min(STEPS.length - 1, Math.round(((v - 0.85) / 0.15) * (STEPS.length - 1))));
                      return <td key={k} title={`chunk ${c}, top_k ${k}: ${pct(v)}`} className="rounded px-2 py-2"
                        style={v === null ? { background: "var(--surface-2)" } : { background: `var(${STEPS[i]})`, color: i >= 3 ? "#ffffff" : "#0b0b0b" }}>{pct(v)}</td>;
                    })}</tr>))}</tbody>
              </table>
              <p className="mt-2 text-xs text-muted">Colour scale: 85% (lightest) to 100% (darkest).</p>
            </div>
          </Panel>
        )}
        <SpendBars data={spendByExperiment(files)} total={index.budget.total} />
      </section>
    </div>
  );
}
