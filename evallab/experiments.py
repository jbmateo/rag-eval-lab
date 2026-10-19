"""Experiment files: a base config plus a grid or explicit variants, expanded into labelled runs."""
import hashlib
import itertools
import json
import subprocess
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError, model_validator


class ExperimentError(Exception):
    """User-facing experiment problem."""


class GateSpec(BaseModel, extra="forbid"):
    max_regressed: int | None = None
    min_accuracy_delta: float | None = None
    max_cost_ratio: float | None = None


class Experiment(BaseModel, extra="forbid"):
    name: str
    description: str = ""
    hypothesis: str | None = None
    system: str
    dataset: str
    subset: str | None = None
    llm: bool = False
    judge: bool = False
    base: dict = {}
    grid: dict[str, list] | None = None
    variants: list[dict] | None = None
    repeats: int = 1
    gate: GateSpec | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.grid is not None and self.variants is not None:
            raise ValueError("use either grid or variants, not both")
        if self.variants is not None and any("label" not in v for v in self.variants):
            raise ValueError("every variant needs a label")
        if self.llm and not (self.hypothesis or "").strip():
            raise ValueError("experiments with llm: true must state a hypothesis before running")
        if self.repeats != 1:
            raise ValueError("repeats > 1 is not supported in v1")
        if self.judge and not self.llm:
            raise ValueError("judge: true requires llm: true")
        return self


def load_experiment(path: Path) -> tuple[Experiment, str]:
    path = Path(path)
    if not path.exists():
        raise ExperimentError(f"No experiment file {path}")
    text = path.read_text()
    try:
        return Experiment.model_validate(yaml.safe_load(text)), text
    except ValidationError as e:
        err = e.errors()[0]
        where = ".".join(str(p) for p in err["loc"]) or "experiment"
        raise ExperimentError(f"{path.name}: {where}: {err['msg'].removeprefix('Value error, ')}") from e


def _fmt(v) -> str:
    return json.dumps(v) if isinstance(v, (list, dict)) else str(v)


def expand(exp: Experiment) -> list[tuple[str, dict]]:
    if exp.grid:
        keys = list(exp.grid)
        return [(",".join(f"{k}={_fmt(v)}" for k, v in zip(keys, values)), {**exp.base, **dict(zip(keys, values))})
                for values in itertools.product(*(exp.grid[k] for k in keys))]
    if exp.variants:
        return [(v["label"], {**exp.base, **{k: x for k, x in v.items() if k != "label"}}) for v in exp.variants]
    return [("base", dict(exp.base))]


def _git(path: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=path.parent, capture_output=True, text=True).stdout.strip()


def experiment_git_state(path: Path) -> tuple[str, bool]:
    """(sha of the last commit touching the file, has uncommitted changes). Untracked → ("", True)."""
    path = Path(path).resolve()
    sha = _git(path, "log", "-1", "--format=%H", "--", path.name)
    dirty = bool(_git(path, "status", "--porcelain", "--", path.name))
    return sha, dirty or not sha


def run_id(dataset_sha: str, subset: str | None, lock_hash: str, system_version: str, judge_model: str,
           rubric_version: str, config: dict, repeat: int) -> str:
    payload = {"dataset_sha": dataset_sha, "subset": subset, "lock_hash": lock_hash,
               "system_version": system_version, "judge_model": judge_model, "rubric_version": rubric_version,
               "config": config, "repeat": repeat}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
