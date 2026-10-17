import Link from "next/link";
import { StatusBadge } from "@/components/StatusBadge";
import { getIndex } from "@/lib/data";
import { pct, usd } from "@/lib/format";

export default async function Home() {
  const index = await getIndex();
  return (
    <div className="space-y-6">
      <div className="max-w-3xl space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Experiments</h1>
        <p className="text-ink-2">
          Each experiment states its hypothesis before it runs, varies one thing, and is scored case by case on a
          versioned dataset. Pick an experiment to compare its runs and see which questions improved or regressed.
        </p>
      </div>
      {index.experiments.length === 0 ? (
        <p className="rounded-lg border border-line bg-surface p-6 text-ink-2">No experiments yet. Run <code>evallab run</code>, then <code>evallab export</code>.</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {index.experiments.map((e) => (
            <li key={e.slug}>
              <Link href={`/experiments/${e.slug}/`}
                className="flex h-full flex-col gap-3 rounded-lg border border-line bg-surface p-4 transition hover:border-series-1">
                <div className="flex items-start justify-between gap-3">
                  <h2 className="font-semibold">{e.name}</h2>
                  <StatusBadge status={e.status} />
                </div>
                <p className="text-sm text-ink-2">{e.hypothesis ?? e.description ?? ""}</p>
                <dl className="mt-auto grid grid-cols-3 gap-2 text-sm">
                  <div><dt className="text-muted">Runs</dt><dd className="num font-medium">{e.runs.length}</dd></div>
                  <div><dt className="text-muted">Best {e.llm ? "accuracy" : "hit@k"}</dt><dd className="num font-medium">{pct(e.best_accuracy)}</dd></div>
                  <div><dt className="text-muted">Spent</dt><dd className="num font-medium">{usd(e.spent, 2)}</dd></div>
                </dl>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
