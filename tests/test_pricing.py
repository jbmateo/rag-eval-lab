import math

import pytest

from evallab import pricing
from tests.conftest import FIXTURES

ROOT = FIXTURES.parent.parent


def test_cost_math():
    p = pricing.load(ROOT / "pricing.yaml")
    assert math.isclose(p.cost("claude-haiku-5-5", 1_000_000, 1_000_000), 0.60)
    assert math.isclose(p.cost("claude-sonnet-5-5", 1_000_000, 1_000_000), 12.00)
    assert math.isclose(p.cost("claude-sonnet-5-5", 4000, 400), 0.012)


def test_unknown_model():
    p = pricing.load(ROOT / "pricing.yaml")
    with pytest.raises(KeyError, match="pricing.yaml"):
        p.cost("gpt-x", 1, 1)
