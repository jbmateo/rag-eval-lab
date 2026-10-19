// Build-time loaders (server only) for public/data written by `evallab export`. Browser fetching is in lib/client.ts.
import "server-only";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { DatasetFile, ExperimentFile, Index, RunFile } from "./types";

const EMPTY_INDEX: Index = { generated_at: "", budget: { total: 0, spent: 0 }, experiments: [], datasets: [] };

async function readJson<T>(rel: string): Promise<T | null> {
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
