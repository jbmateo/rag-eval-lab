"use client";
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ms, pct, shortLabels, usd } from "@/lib/format";
import type { Run } from "@/lib/types";

const CHARTS = [
  { key: "accuracy", title: (a: string) => a, fmt: (v: number) => pct(v) },
  { key: "latency_p50_ms", title: () => "p50 latency (uncached)", fmt: (v: number) => ms(v) },
  { key: "cost_per_case", title: () => "cost per case", fmt: (v: number) => usd(v) },
] as const;

export function MetricBars({ runs, accLabel }: { runs: Run[]; accLabel: string }) {
  const height = Math.max(120, runs.length * 30 + 40);
  const short = shortLabels(runs.map((r) => r.label));
  return (
    <section className="grid gap-6 md:grid-cols-3">
      {CHARTS.map((c) => {
        const data = runs.map((r) => ({ label: short.get(r.label)!, v: (r.summary?.[c.key] ?? null) as number | null }));
        return (
          <figure key={c.key} className="min-w-0 rounded-lg border border-line bg-surface p-4">
            <figcaption className="mb-2 font-semibold">{c.title(accLabel)}</figcaption>
            {data.every((d) => d.v === null) ? <p className="text-sm text-muted">—</p> : (
              <div style={{ height }}>
                <ResponsiveContainer>
                  <BarChart data={data} layout="vertical" margin={{ top: 0, right: 56, bottom: 0, left: 0 }} barCategoryGap={2}>
                    <CartesianGrid stroke="var(--grid)" horizontal={false} />
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="label" width={150} tick={{ fill: "var(--ink-2)", fontSize: 12 }} stroke="var(--axis)" />
                    <Tooltip cursor={{ fill: "var(--surface-2)" }} formatter={(v: number) => [c.fmt(v), c.title(accLabel)]}
                      contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--ink)" }} />
                    <Bar dataKey="v" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false}>
                      <LabelList dataKey="v" position="right" formatter={(v: number) => c.fmt(v)} fill="var(--ink-2)" fontSize={12} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </figure>
        );
      })}
    </section>
  );
}
