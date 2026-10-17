import { usd } from "@/lib/format";

export function BudgetBar({ spent, total }: { spent: number; total: number }) {
  const share = total > 0 ? Math.min(1, spent / total) : 0;
  return (
    <div className="flex items-center gap-2 text-sm" title="Actual API spend across all runs, against the project budget">
      <span className="text-ink-2">API spend</span>
      <span className="num font-medium">{usd(spent, 2)} of {usd(total, 2)} spent</span>
      <span className="relative h-1.5 w-20 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <span className="absolute inset-y-0 left-0 rounded-full bg-series-1" style={{ width: `${share * 100}%` }} />
      </span>
    </div>
  );
}
