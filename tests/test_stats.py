import json
import math

from evallab.stats import Mulberry32, mcnemar_exact, mde_paired, paired_bootstrap_ci, verdict
from tests.conftest import FIXTURES

VECTORS = json.loads((FIXTURES / "stats_vectors.json").read_text())


def test_mulberry32_vector():
    for seed, expected in ((0, VECTORS["seed0"]), (42, VECTORS["seed42"])):
        rng = Mulberry32(seed)
        assert [rng.next_u32() for _ in range(5)] == expected


def test_mcnemar_known():
    assert mcnemar_exact(0, 0) == 1.0
    assert math.isclose(mcnemar_exact(1, 5), 0.21875)
    assert math.isclose(mcnemar_exact(0, 6), 0.03125)
    assert mcnemar_exact(5, 1) == mcnemar_exact(1, 5)
    assert mcnemar_exact(3, 3) == 1.0


def test_bootstrap_reproducible_and_brackets():
    base = [1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0]
    cand = [1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0]
    a = paired_bootstrap_ci(base, cand, resamples=2000, seed=0)
    assert a == paired_bootstrap_ci(base, cand, resamples=2000, seed=0)
    mean, lo, hi = a
    assert math.isclose(mean, 0.2) and lo <= mean <= hi and lo >= 0.0


def test_bootstrap_degenerate():
    assert paired_bootstrap_ci([1.0], [0.0]) == (-1.0, None, None)
    assert paired_bootstrap_ci([], []) == (None, None, None)


def test_mde():
    assert math.isclose(mde_paired(60, 6), 2.80 * math.sqrt(0.1 / 60))
    assert math.isclose(mde_paired(60, 0), 2.80 * math.sqrt((1 / 60) / 60))
    assert mde_paired(0, 0) is None


def test_verdict():
    assert verdict(0.01, 0.2) == "better" and verdict(-0.2, -0.01) == "worse"
    assert verdict(-0.1, 0.1) == "no detectable difference" and verdict(None, None) == "no detectable difference"
    assert verdict(0.01, 0.2, higher_is_better=False) == "worse"
