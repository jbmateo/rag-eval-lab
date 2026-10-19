"use client";
// Overview charts. Colour slots 1–3 (validated all-pairs, light and dark); text always in ink tokens;
// every chart has a legend or direct labels and a "Show data" table.
import {
  Bar, BarChart, CartesianGrid, ErrorBar, LabelList, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { pct, usd } from "@/lib/format";

const AXIS = { stroke: "var(--axis)", tick: { fill: "var(--muted)", fontSize: 12 } };
const TIP = {
  contentStyle: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--ink)", fontSize: 13 },
  labelStyle: { color: "var(--ink)", fontWeight: 600 },
  itemStyle: { color: "var(--ink-2)" },
};
const LEGEND = { wrapperStyle: { fontSize: 13, color: "var(--ink-2)" }, iconType: "circle" as const, iconSize: 9 };
const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

export function Panel({ title, note, children, table }: {
  title: string; note?: string; children: React.ReactNode; table: { head: string[]; rows: (string | number)[][] };
}) {
  return (
    <figure className="min-w-0 rounded-lg border border-line bg-surface p-4">
      <figcaption className="mb-1 font-semibold">{title}</figcaption>
      {note && <p className="mb-3 text-sm text-ink-2">{note}</p>}
      {children}
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-ink-2 hover:text-ink">Show data</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="num w-full text-left">
            <thead className="text-muted"><tr>{table.head.map((h) => <th key={h} className="py-1 pr-4 font-medium">{h}</th>)}</tr></thead>
            <tbody>{table.rows.map((r, i) => (
              <tr key={i} className="border-t border-line">{r.map((c, j) => <td key={j} className="py-1 pr-4">{c}</td>)}</tr>))}</tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

const short = (model: string) => model.replace("claude-", "").replace(/-5-5$/, " 5.5").replace(/^./, (c) => c.toUpperCase());

export function ModelCharts({ data }: {
  data: { model: string; accuracy: number | null; ci: [number | null, number | null]; costPerCase: number | null }[];
}) {
  const rows = data.map((d) => ({
    name: short(d.model), accuracy: d.accuracy, cost: d.costPerCase,
    err: d.accuracy === null ? [0, 0] : [d.accuracy - (d.ci[0] ?? d.accuracy), (d.ci[1] ?? d.accuracy) - d.accuracy],
  }));
  const ratio = data.length === 2 && data[0].costPerCase && data[1].costPerCase
    ? Math.min(data[0].costPerCase, data[1].costPerCase) / Math.max(data[0].costPerCase, data[1].costPerCase) : null;
  return (
    <Panel title="Sonnet vs Haiku (H5)"
      note={`Same pipeline, judge and 60 questions; only the answering model changes.${ratio ? ` The cheaper model costs ${pct(ratio)} as much per case.` : ""}`}
      table={{ head: ["model", "accuracy", "95% CI", "cost per case"], rows: data.map((d) =>
        [short(d.model), pct(d.accuracy), `${pct(d.ci[0], 0)}–${pct(d.ci[1], 0)}`, usd(d.costPerCase)]) }}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-sm font-medium text-ink-2">Accuracy (95% CI)</p>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={rows} margin={{ top: 20, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="name" {...AXIS} />
                <YAxis domain={[0, 1]} tickFormatter={(v) => pct(v, 0)} width={40} {...AXIS} />
                <Tooltip {...TIP} cursor={{ fill: "var(--surface-2)" }} formatter={(v: number) => [pct(v), "accuracy"]} />
                <Bar dataKey="accuracy" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false}>
                  <ErrorBar dataKey="err" stroke="var(--ink-2)" strokeWidth={1.5} width={8} />
                  <LabelList dataKey="accuracy" position="center" formatter={(v: number) => pct(v)} fill="#ffffff" fontSize={12} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <p className="mb-1 text-sm font-medium text-ink-2">Cost per case (answering model)</p>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={rows} margin={{ top: 20, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="name" {...AXIS} />
                <YAxis tickFormatter={(v) => usd(v, 3)} width={52} {...AXIS} />
                <Tooltip {...TIP} cursor={{ fill: "var(--surface-2)" }} formatter={(v: number) => [usd(v), "cost per case"]} />
                <Bar dataKey="cost" fill="var(--series-2)" radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false}>
                  <LabelList dataKey="cost" position="top" formatter={(v: number) => usd(v)} fill="var(--ink-2)" fontSize={12} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </Panel>
  );
}

function PctLines({ data, x, xLabel, lines, xFmt, yMin = 0 }: {
  data: Record<string, number | null>[]; x: string; xLabel: string; xFmt?: (v: number) => string; yMin?: number;
  lines: { key: string; name: string }[];
}) {
  return (
    <div className="h-64">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 20, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey={x} type="number" domain={["dataMin", "dataMax"]} ticks={data.map((d) => d[x] as number)}
            tickFormatter={xFmt} {...AXIS} label={{ value: xLabel, position: "bottom", fill: "var(--muted)", fontSize: 12 }} />
          <YAxis domain={[yMin, 1]} ticks={Array.from({ length: Math.round((1 - yMin) / (yMin ? 0.05 : 0.25)) + 1 }, (_, i) => yMin + i * (yMin ? 0.05 : 0.25))}
            tickFormatter={(v) => pct(v, 0)} width={44} {...AXIS} />
          <Tooltip {...TIP} labelFormatter={(v) => `${xLabel} ${xFmt ? xFmt(v as number) : v}`} formatter={(v: number, n) => [pct(v), n]} />
          <Legend {...LEGEND} verticalAlign="top" align="right" height={28} />
          {lines.map((l, i) => (
            <Line key={l.key} type="linear" dataKey={l.key} name={l.name} stroke={SERIES[i]} strokeWidth={2}
              dot={{ r: 4, fill: SERIES[i], stroke: "var(--surface)", strokeWidth: 2 }} activeDot={{ r: 6 }} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ThresholdChart({ data }: { data: { threshold: number; answerRate: number | null; refusalRecall: number | null; accuracy: number | null }[] }) {
  return (
    <Panel title="Similarity gate threshold (H2′ + exploratory sweep)"
      note="Refusals stay at 100% at every threshold — the model already declines every unanswerable question — so raising the gate only blocks answerable ones."
      table={{ head: ["min_similarity", "answer rate", "refusal recall", "accuracy"], rows: data.map((d) =>
        [d.threshold.toFixed(2), pct(d.answerRate), pct(d.refusalRecall), pct(d.accuracy)]) }}>
      <PctLines data={data} x="threshold" xLabel="min_similarity" xFmt={(v) => v.toFixed(2)}
        lines={[{ key: "answerRate", name: "answer rate" }, { key: "refusalRecall", name: "refusal recall" }, { key: "accuracy", name: "accuracy" }]} />
    </Panel>
  );
}

export function ChunkCharts({ data }: { data: { chunk: number; hit: number | null; answerRate: number | null; accuracy: number | null; costPerCase: number | null }[] }) {
  return (
    <Panel title="Chunk size (H4)" note="Accuracy is flat across chunk sizes while cost per case grows with the context sent. (Axis starts at 75%.)"
      table={{ head: ["chunk_chars", "hit@8", "answer rate", "accuracy", "cost per case"], rows: data.map((d) =>
        [d.chunk, pct(d.hit), pct(d.answerRate), pct(d.accuracy), usd(d.costPerCase)]) }}>
      <PctLines data={data} x="chunk" xLabel="chunk_chars" yMin={0.75}
        lines={[{ key: "hit", name: "hit@8" }, { key: "answerRate", name: "answer rate" }, { key: "accuracy", name: "accuracy" }]} />
      <p className="mb-1 mt-3 text-sm font-medium text-ink-2">Cost per case</p>
      <div className="h-32">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 64, bottom: 0, left: 0 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="chunk" width={48} {...AXIS} />
            <Tooltip {...TIP} cursor={{ fill: "var(--surface-2)" }} formatter={(v: number) => [usd(v), "cost per case"]} labelFormatter={(v) => `${v} chars`} />
            <Bar dataKey="costPerCase" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={16} isAnimationActive={false}>
              <LabelList dataKey="costPerCase" position="right" formatter={(v: number) => usd(v, 5)} fill="var(--ink-2)" fontSize={12} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

export function RetrievalModes({ data }: { data: { tag: string; vector: number | null; bm25: number | null; hybrid: number | null }[] }) {
  return (
    <Panel title="Retrieval mode by question type (H1)" note="hit@8 over answerable questions. Hybrid matches the best single mode on both types."
      table={{ head: ["question type", "vector", "bm25", "hybrid"], rows: data.map((d) => [d.tag, pct(d.vector), pct(d.bm25), pct(d.hybrid)]) }}>
      <div className="h-64">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barGap={2}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="tag" {...AXIS} />
            <YAxis domain={[0, 1]} tickFormatter={(v) => pct(v, 0)} width={44} {...AXIS} />
            <Tooltip {...TIP} cursor={{ fill: "var(--surface-2)" }} formatter={(v: number, n) => [pct(v), n]} />
            <Legend {...LEGEND} verticalAlign="top" align="right" height={28} />
            {(["vector", "bm25", "hybrid"] as const).map((m, i) => (
              <Bar key={m} dataKey={m} fill={SERIES[i]} radius={[4, 4, 0, 0]} maxBarSize={32} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

export function SpendBars({ data, total }: { data: { experiment: string; spent: number }[]; total: number }) {
  return (
    <Panel title="Where the API budget went" note={`Actual spend per experiment against the ${usd(total, 2)} cap; everything else ran from cache or without an LLM.`}
      table={{ head: ["experiment", "spent"], rows: data.map((d) => [d.experiment, usd(d.spent, 4)]) }}>
      <div style={{ height: Math.max(120, data.length * 34 + 16) }}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 64, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid)" horizontal={false} />
            <XAxis type="number" hide domain={[0, "dataMax"]} />
            <YAxis type="category" dataKey="experiment" width={104} {...AXIS} tick={{ fill: "var(--ink-2)", fontSize: 12 }} />
            <Tooltip {...TIP} cursor={{ fill: "var(--surface-2)" }} formatter={(v: number) => [usd(v, 4), "spent"]} />
            <Bar dataKey="spent" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false}>
              <LabelList dataKey="spent" position="right" formatter={(v: number) => usd(v, 3)} fill="var(--ink-2)" fontSize={12} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
