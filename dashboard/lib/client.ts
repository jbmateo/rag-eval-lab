// Browser-side loaders for the exported JSON.
import type { DatasetFile, ExperimentFile, RunFile } from "./types";

const runCache = new Map<string, Promise<RunFile>>();

export function fetchRun(runId: string): Promise<RunFile> {
  if (!runCache.has(runId)) {
    const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
    runCache.set(runId, fetch(`${base}/data/runs/${runId}.json`).then((r) => {
      if (!r.ok) throw new Error(`Run ${runId} not found (${r.status})`);
      return r.json() as Promise<RunFile>;
    }));
  }
  return runCache.get(runId)!;
}

export async function fetchDataset(name: string): Promise<DatasetFile | null> {
  const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
  const r = await fetch(`${base}/data/datasets/${name}.json`);
  return r.ok ? ((await r.json()) as DatasetFile) : null;
}

export async function fetchExperiment(slug: string): Promise<ExperimentFile | null> {
  const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
  const r = await fetch(`${base}/data/experiments/${slug}.json`);
  return r.ok ? ((await r.json()) as ExperimentFile) : null;
}
