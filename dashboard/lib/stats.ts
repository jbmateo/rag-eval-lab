// Port of evallab/stats.py. Every operation happens in the same order as the Python so results are identical.

export class Mulberry32 {
  private a: number;
  constructor(seed: number) { this.a = seed >>> 0; }
  nextU32(): number {
    this.a = (this.a + 0x6d2b79f5) >>> 0;
    let t = this.a;
    t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
    t = (t ^ ((t + Math.imul(t ^ (t >>> 7), t | 61)) >>> 0)) >>> 0;
    return (t ^ (t >>> 14)) >>> 0;
  }
  random(): number { return this.nextU32() / 2 ** 32; }
}

export function fsumLtr(values: number[]): number {
  let total = 0;
  for (const v of values) total += v;
  return total;
}

export function mcnemarExact(b: number, c: number): number {
  const n = b + c;
  if (n === 0) return 1;
  let term = 0.5 ** n;
  let tail = 0;
  for (let i = 0; i <= Math.min(b, c); i++) {
    tail += term;
    term = (term * (n - i)) / (i + 1);
  }
  return Math.min(1, 2 * tail);
}

const roundHalfUp = (x: number) => Math.trunc(x + 0.5);

export function pairedBootstrapCi(base: number[], cand: number[], resamples = 10_000, seed = 0):
  [number | null, number | null, number | null] {
  const n = base.length;
  if (n === 0) return [null, null, null];
  const deltas = base.map((b, i) => cand[i] - b);
  const mean = fsumLtr(deltas) / n;
  if (n < 2) return [mean, null, null];
  const rng = new Mulberry32(seed);
  const means: number[] = [];
  for (let r = 0; r < resamples; r++) {
    let s = 0;
    for (let j = 0; j < n; j++) s += deltas[Math.trunc(rng.random() * n)];
    means.push(s / n);
  }
  means.sort((x, y) => x - y);
  return [mean, means[roundHalfUp(0.025 * (resamples - 1))], means[roundHalfUp(0.975 * (resamples - 1))]];
}

export function mdePaired(n: number, discordant: number): number | null {
  if (n === 0) return null;
  return 2.8 * Math.sqrt(Math.max(discordant / n, 1 / n) / n);
}

export function verdict(lo: number | null, hi: number | null, higherIsBetter = true): string {
  if (lo === null || hi === null) return "no detectable difference";
  if (lo > 0) return higherIsBetter ? "better" : "worse";
  if (hi < 0) return higherIsBetter ? "worse" : "better";
  return "no detectable difference";
}
