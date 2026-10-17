"use client";
import { CartesianGrid, ErrorBar, LabelList, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { pct, usd } from "@/lib/format";
import type { Run } from "@/lib/types";

type Point = { label: string; cost: number; acc: number; err: [number, number]; front: boolean };

/** Runs no other run beats on both cost (lower) and accuracy (higher). */
function paretoFront(points: Omit<Point, "front">[]): Set<string> {
  return new Set(points.filter((p) => !points.some((q) =>
    q !== p && q.cost <= p.cost && q.acc >= p.acc && (q.cost < p.cost || q.acc > p.acc))).map((p) => p.label));
}

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-sm shadow-sm">
      <div className="font-medium">{p.label}</div>
      <div className="num text-ink-2">accuracy {pct(p.acc)} (95% CI {pct(p.acc - p.err[0])}–{pct(p.acc + p.err[1])})</div>
      <div className="num text-ink-2">cost per case {usd(p.cost)}</div>
      {p.front && <div className="text-ink-2">On the cost/accuracy front</div>}
    </div>
  );
}

export function CostAccuracyScatter({ runs, accLabel }: { runs: Run[]; accLabel: string }) {
  const raw = runs.filter((r) => r.summary?.accuracy != null && r.summary?.cost_per_case != null).map((r) => {
    const acc = r.summary!.accuracy as number;
    const [lo, hi] = r.summary!.accuracy_ci ?? [acc, acc];
    return { label: r.label, cost: r.summary!.cost_per_case as unknown as number, acc,
      err: [acc - (lo ?? acc), (hi ?? acc) - acc] as [number, number] };
  });
  const front = paretoFront(raw);
  const points: Point[] = raw.map((p) => ({ ...p, front: front.has(p.label) }));
  const frontPts = points.filter((p) => p.front).sort((a, b) => a.cost - b.cost);
  const others = points.filter((p) => !p.front);
  return (
    <figure className="min-w-0 rounded-lg border border-line bg-surface p-4">
      <figcaption className="mb-1 font-semibold">Cost per case vs {accLabel}</figcaption>
      <p className="mb-3 text-sm text-ink-2">Bars are 95% bootstrap intervals. The line joins runs no other run beats on both cost and {accLabel}.</p>
      <div className="h-72">
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 16, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid stroke="var(--grid)" strokeWidth={1} vertical={false} />
            <XAxis type="number" dataKey="cost" name="cost" domain={[0, (max: number) => (max > 0 ? max * 1.25 : 1)]} tickFormatter={(v) => usd(v, 4)} stroke="var(--axis)"
              tick={{ fill: "var(--muted)", fontSize: 12 }} label={{ value: "cost per case (USD)", position: "bottom", fill: "var(--muted)", fontSize: 12 }} />
            <YAxis type="number" dataKey="acc" domain={[0, 1]} tickFormatter={(v) => pct(v, 0)} stroke="var(--axis)"
              tick={{ fill: "var(--muted)", fontSize: 12 }} width={44} />
            <Tooltip content={<Tip />} cursor={{ stroke: "var(--axis)" }} />
            <Scatter data={others} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2}>
              <ErrorBar dataKey="err" direction="y" stroke="var(--series-1)" strokeWidth={1.5} width={6} />
            </Scatter>
            <Scatter data={frontPts} fill="var(--series-2)" stroke="var(--surface)" strokeWidth={2}
              line={{ stroke: "var(--series-2)", strokeWidth: 2 }}>
              <ErrorBar dataKey="err" direction="y" stroke="var(--series-2)" strokeWidth={1.5} width={6} />
              <LabelList dataKey="label" position="left" offset={10} fill="var(--ink-2)" fontSize={12} />
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex gap-4 text-sm text-ink-2">
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-[var(--series-2)]" />best tradeoffs (labelled)</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-[var(--series-1)]" />other runs</span>
      </div>
    </figure>
  );
}
