"""Statistics shared with the dashboard's TypeScript port. Pure Python so both sides match exactly."""
import math


class Mulberry32:
    """Small seeded PRNG; identical sequence to dashboard/lib/stats.ts."""

    def __init__(self, seed: int):
        self.a = seed & 0xFFFFFFFF

    def next_u32(self) -> int:
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = _imul(t ^ (t >> 15), t | 1)
        t ^= (t + _imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF
        return (t ^ (t >> 14)) & 0xFFFFFFFF

    def random(self) -> float:
        return self.next_u32() / 2**32

    def shuffle(self, items: list) -> list:
        """Fisher-Yates from the end; returns a new list."""
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = int(self.random() * (i + 1))
            out[i], out[j] = out[j], out[i]
        return out


def _imul(x: int, y: int) -> int:
    return (x * y) & 0xFFFFFFFF


# Every float sum below is an explicit left-to-right loop: Python 3.12's sum() uses compensated
# summation, which JavaScript doesn't, and the dashboard port must produce identical numbers.


def fsum_ltr(values) -> float:
    total = 0.0
    for v in values:
        total += v
    return total


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar test on the discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    term = 0.5 ** n
    tail = 0.0
    for i in range(min(b, c) + 1):
        tail += term
        term = term * (n - i) / (i + 1)
    return min(1.0, 2.0 * tail)


def _round_half_up(x: float) -> int:
    return int(x + 0.5)


def paired_bootstrap_ci(base: list[float], cand: list[float], resamples: int = 10_000,
                        seed: int = 0) -> tuple[float | None, float | None, float | None]:
    """(mean of cand − base, 2.5th percentile, 97.5th percentile) over paired resamples."""
    n = len(base)
    if n == 0:
        return None, None, None
    deltas = [c - b for b, c in zip(base, cand)]
    mean = fsum_ltr(deltas) / n
    if n < 2:
        return mean, None, None
    rng = Mulberry32(seed)
    means = []
    for _ in range(resamples):
        s = 0.0
        for _ in range(n):
            s += deltas[int(rng.random() * n)]
        means.append(s / n)
    means.sort()
    return mean, means[_round_half_up(0.025 * (resamples - 1))], means[_round_half_up(0.975 * (resamples - 1))]


def mde_paired(n: int, discordant: int) -> float | None:
    """Minimum detectable change in accuracy at 80% power, α = 0.05, for n paired cases."""
    if n == 0:
        return None
    return 2.80 * math.sqrt(max(discordant / n, 1 / n) / n)


def verdict(lo: float | None, hi: float | None, higher_is_better: bool = True) -> str:
    if lo is None or hi is None:
        return "no detectable difference"
    if lo > 0:
        return "better" if higher_is_better else "worse"
    if hi < 0:
        return "worse" if higher_is_better else "better"
    return "no detectable difference"
