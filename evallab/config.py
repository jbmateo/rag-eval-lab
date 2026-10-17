"""Project settings from evallab.toml, with the API key from the environment or .env."""
import os
import tomllib
from pathlib import Path

from pydantic import BaseModel

CONFIG_NAME = "evallab.toml"


class Settings(BaseModel):
    root: Path
    budget_total_usd: float
    judge_model: str
    judge_rubric_version: str
    store_path: Path
    cache_dir: Path
    export_dir: Path
    systems: dict[str, dict]
    ci_baseline_run: str = ""
    anthropic_api_key: str = ""


def find_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / CONFIG_NAME).exists():
            return d
    raise FileNotFoundError(f"No {CONFIG_NAME} found in {start} or any parent directory")


def _dotenv_key(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text().splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() == "ANTHROPIC_API_KEY":
            return value.strip().strip('"').strip("'")
    return ""


def load_settings(root: Path | None = None) -> Settings:
    root = Path(root).resolve() if root is not None else find_root(Path.cwd().resolve())
    path = root / CONFIG_NAME
    if not path.exists():
        raise FileNotFoundError(f"No {CONFIG_NAME} in {root}")
    raw = tomllib.loads(path.read_text())
    paths = raw.get("paths", {})
    return Settings(
        root=root,
        budget_total_usd=float(raw["budget"]["total_usd"]),
        judge_model=raw["judge"]["model"],
        judge_rubric_version=raw["judge"]["rubric_version"],
        store_path=root / paths.get("store", "results/evallab.db"),
        cache_dir=root / paths.get("cache", "cache"),
        export_dir=root / paths.get("export", "dashboard/public/data"),
        systems=raw.get("systems", {}),
        ci_baseline_run=raw.get("ci", {}).get("baseline_run", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or _dotenv_key(root / ".env"),
    )
