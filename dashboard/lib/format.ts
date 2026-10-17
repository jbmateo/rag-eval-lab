export const dash = "—";

export function pct(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined || Number.isNaN(v) ? dash : `${(v * 100).toFixed(digits)}%`;
}
export function num(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined || Number.isNaN(v) ? dash : v.toFixed(digits);
}
export function usd(v: number | null | undefined, digits = 4): string {
  return v === null || v === undefined || Number.isNaN(v) ? dash : `$${v.toFixed(digits)}`;
}
export function ms(v: number | null | undefined): string {
  return v === null || v === undefined || Number.isNaN(v) ? dash : `${Math.round(v)} ms`;
}
export function signedPts(v: number | null | undefined): string {
  return v === null || v === undefined ? dash : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)} pts`;
}
export function value(v: unknown): string {
  if (v === null || v === undefined) return dash;
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Config keys whose values differ across the given configs, in first-seen order. */
export function varyingKeys(configs: Record<string, unknown>[]): string[] {
  const keys: string[] = [];
  for (const c of configs) for (const k of Object.keys(c)) if (!keys.includes(k)) keys.push(k);
  return keys.filter((k) => new Set(configs.map((c) => JSON.stringify(c[k] ?? null))).size > 1);
}

const norm = (t: string) => t.split(/\s+/).filter(Boolean).join(" ").toLowerCase();

/** Same rule as evallab.datasets.evidence_matches: document equal, whole evidence or first 8 words contained. */
export function evidenceMatches(doc: string, text: string, e: { document: string; evidence: string }): boolean {
  if (doc !== e.document) return false;
  const t = norm(text), ev = norm(e.evidence);
  return t.includes(ev) || t.includes(ev.split(" ").slice(0, 8).join(" "));
}

/** Same as evallab.export.slugify. */
export function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}
