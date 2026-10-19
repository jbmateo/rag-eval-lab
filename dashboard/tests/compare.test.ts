import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { compareRuns } from "../lib/compare";
import { Mulberry32, mcnemarExact, mdePaired, pairedBootstrapCi } from "../lib/stats";

const FIX = join(__dirname, "..", "..", "tests", "fixtures");
const load = (name: string) => JSON.parse(readFileSync(join(FIX, name), "utf8"));

describe("stats parity with Python", () => {
  it("mulberry32 matches python vectors", () => {
    const v = load("stats_vectors.json");
    for (const [seed, expected] of [[0, v.seed0], [42, v.seed42]] as const) {
      const rng = new Mulberry32(seed);
      expect(Array.from({ length: 5 }, () => rng.nextU32())).toEqual(expected);
    }
  });

  it("mcnemar and mde known values", () => {
    expect(mcnemarExact(0, 0)).toBe(1);
    expect(mcnemarExact(1, 5)).toBe(0.21875);
    expect(mcnemarExact(0, 6)).toBe(0.03125);
    expect(mdePaired(60, 6)).toBe(2.8 * Math.sqrt(0.1 / 60));
    expect(mdePaired(0, 0)).toBeNull();
  });

  it("bootstrap degenerate inputs", () => {
    expect(pairedBootstrapCi([], [])).toEqual([null, null, null]);
    expect(pairedBootstrapCi([1], [0])).toEqual([-1, null, null]);
  });
});

describe("compareRuns", () => {
  it("matches the python fixture exactly", () => {
    const pair = load("compare_pair.json");
    const expected = load("compare_expected.json");
    const got = compareRuns(pair.base, pair.base_rows, pair.cand, pair.cand_rows);
    expect(JSON.parse(JSON.stringify(got))).toEqual(expected);
  });

  it("refuses incomplete runs unless allowed", () => {
    const pair = load("compare_pair.json");
    pair.cand.status = "partial";
    expect(() => compareRuns(pair.base, pair.base_rows, pair.cand, pair.cand_rows)).toThrow(/allow-incomplete/);
    const r = compareRuns(pair.base, pair.base_rows, pair.cand, pair.cand_rows, true);
    expect(r.warnings).toContain("candidate run is partial");
  });
});
