import { describe, expect, it } from "vitest";
import { shortLabels, slugify } from "../lib/format";

describe("format helpers", () => {
  it("drops a shared single-key prefix only", () => {
    expect([...shortLabels(["model=a", "model=b"]).values()]).toEqual(["a", "b"]);
    expect([...shortLabels(["a=1,b=2", "a=2,b=2"]).values()]).toEqual(["a=1,b=2", "a=2,b=2"]);
    expect([...shortLabels(["baseline", "aggressive"]).values()]).toEqual(["baseline", "aggressive"]);
  });
  it("slugify matches evallab.export.slugify", () => {
    expect(slugify("My Sweep/2")).toBe("my-sweep-2");
  });
});

import { labelFor } from "../lib/format";

describe("labelFor", () => {
  it("uses the label from the experiment the user came from for a shared run", () => {
    const exp = { runs: [{ run_id: "r1", label: "model=claude-haiku-5-5" }] };
    expect(labelFor(exp, "r1", "base")).toBe("model=claude-haiku-5-5");
    expect(labelFor(exp, "r2", "own")).toBe("own");
    expect(labelFor(null, "r1", "base")).toBe("base");
  });
});
