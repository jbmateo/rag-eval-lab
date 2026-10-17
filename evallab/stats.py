"""Statistics shared with the dashboard's TypeScript port. Pure Python so both sides match exactly."""


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
