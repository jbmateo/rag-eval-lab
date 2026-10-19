import { Suspense } from "react";
import { CompareView } from "@/components/CompareView";

export default function ComparePage() {
  return (
    <Suspense fallback={<p className="text-ink-2">Loading…</p>}>
      <CompareView />
    </Suspense>
  );
}
