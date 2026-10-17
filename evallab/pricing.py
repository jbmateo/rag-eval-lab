"""Token → USD from pricing.yaml (USD per million tokens)."""
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Pricing:
    as_of: str
    models: dict[str, dict[str, float]]

    def cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        if model not in self.models:
            raise KeyError(f"No price for model {model!r} in pricing.yaml")
        p = self.models[model]
        return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def load(path: Path) -> Pricing:
    raw = yaml.safe_load(Path(path).read_text())
    return Pricing(as_of=str(raw["as_of"]), models=raw["models"])
