import { notFound } from "next/navigation";
import { getDataset, getIndex, getRunFile } from "@/lib/data";
import type { Run } from "@/lib/types";

export const dynamicParams = false;

export async function generateStaticParams() {
  const index = await getIndex();
  return index.datasets.length ? index.datasets.map((name) => ({ name })) : [{ name: "none" }];
}

export default async function DatasetPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const ds = await getDataset(name);
  if (!ds) notFound();
  const index = await getIndex();
  const runIds = [...new Set(index.experiments.flatMap((e) => e.runs))];
  const files = (await Promise.all(runIds.map(getRunFile))).filter((f) => f && f.run.dataset.startsWith(`${name}@`));
  const latest = ds.manifest.versions[ds.manifest.versions.length - 1];
  const cases = ds.versions[latest.version] ?? [];
  const runs: Run[] = files.map((f) => f!.run);
  const pass = new Map(files.flatMap((f) => f!.cases.map((c) => [`${f!.run.run_id}:${c.case_id}`, c.pass] as const)));
  const tags = [...new Set(cases.map((c) => c.tag))].sort();
  return (
    <div className="space-y-8">
      <section className="max-w-3xl space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Dataset: {ds.name}</h1>
        <p className="text-ink-2">Published versions never change; any edit becomes a new version with a changelog line.</p>
      </section>
      <section className="overflow-x-auto rounded-lg border border-line bg-surface">
        <table className="num w-full text-sm">
          <thead className="text-left text-muted"><tr className="border-b border-line">
            {["version", "cases", "created", "parent", "changes"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
          <tbody>{ds.manifest.versions.map((v) => (
            <tr key={v.version} className="border-b border-line last:border-0">
              <td className="px-3 py-2 font-medium">{v.version}</td><td className="px-3 py-2">{v.cases}</td><td className="px-3 py-2">{v.created}</td>
              <td className="px-3 py-2">{v.parent ?? "—"}</td><td className="px-3 py-2 text-ink-2">{v.changes}</td></tr>))}</tbody>
        </table>
      </section>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Cases in {latest.version}</h2>
        <p className="text-sm text-ink-2">Marks show each run&apos;s result: ✓ pass, ✗ fail, · not scored. Hover a mark for the run.</p>
        {tags.map((tag) => (
          <details key={tag} className="rounded-lg border border-line bg-surface" open={tags.length <= 3}>
            <summary className="cursor-pointer px-4 py-2 font-medium">{tag} <span className="text-muted">({cases.filter((c) => c.tag === tag).length})</span></summary>
            <ul className="divide-y divide-[var(--border)]">
              {cases.filter((c) => c.tag === tag).map((c) => (
                <li key={c.id} className="flex flex-wrap gap-x-4 gap-y-1 px-4 py-2 text-sm">
                  <span className="num w-12 text-muted">{c.id}</span>
                  <span className="min-w-0 flex-1">{c.question}</span>
                  <span className="num flex flex-wrap gap-1" aria-label="results per run">
                    {runs.map((r) => {
                      const p = pass.get(`${r.run_id}:${c.id}`);
                      const mark = p === undefined || p === null ? "·" : p ? "✓" : "✗";
                      return <span key={r.run_id} title={`${r.experiment}:${r.label} — ${p ? "pass" : p === false ? "fail" : "not scored"}`}
                        className={p ? "text-good" : p === false ? "text-critical" : "text-muted"}>{mark}</span>;
                    })}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </section>
    </div>
  );
}
