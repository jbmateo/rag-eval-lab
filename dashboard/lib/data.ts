// Build-time loaders read public/data written by `evallab export`; the browser fetches run files on demand.
import type { DatasetFile, ExperimentFile, Index, RunFile } from "./types";

const EMPTY_INDEX: Index = { generated_at: "", budget: { total: 0, spent: 0 }, experiments: [], datasets: [] };

async function readJson<T>(rel: string): Promise<T | null> {
  const { readFile } = await import("node:fs/promises");
  const { join } = await import("node:path");
  try {
    return JSON.parse(await readFile(join(process.cwd(), "public", "data", rel), "utf8")) as T;
  } catch {
    return null;
  }
}

export async function getIndex(): Promise<Index> {
  return (await readJson<Index>("index.json")) ?? EMPTY_INDEX;
}

export async function getExperiment(slug: string): Promise<ExperimentFile | null> {
  return readJson<ExperimentFile>(`experiments/${slug}.json`);
}

export async function getDataset(name: string): Promise<DatasetFile | null> {
  return readJson<DatasetFile>(`datasets/${name}.json`);
}

export async function getRunFile(runId: string): Promise<RunFile | null> {
  return readJson<RunFile>(`runs/${runId}.json`);
}

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
