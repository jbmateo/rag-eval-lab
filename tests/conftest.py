import json
from pathlib import Path

import pytest

from evallab.adapters.base import Corpus

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_corpus() -> Corpus:
    path = FIXTURES / "corpus"
    return Corpus(name="fixture", path=path, lock_hash="test", files=sorted(path.iterdir()))


@pytest.fixture
def fixture_questions() -> list[dict]:
    return [json.loads(line) for line in (FIXTURES / "questions.jsonl").read_text().splitlines() if line.strip()]


@pytest.fixture
def make_settings():
    from evallab.config import Settings

    def _make(root: Path, **over) -> Settings:
        base = dict(root=root, budget_total_usd=1.0, judge_model="fake", judge_rubric_version="v1",
                    store_path=root / "results/evallab.db", cache_dir=root / "cache",
                    export_dir=root / "dashboard/public/data", systems={})
        return Settings(**{**base, **over})

    return _make


@pytest.fixture
def lab(tmp_path, make_settings):
    """A tmp project root with a copy of the fixture corpus; returns settings."""
    import shutil

    shutil.copytree(FIXTURES / "corpus", tmp_path / "corpus")
    return make_settings(tmp_path)


LAB_TOML = '[budget]\ntotal_usd = 1.0\n[judge]\nmodel = "fake"\nrubric_version = "v1"\n'


def git(root: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def git_lab(lab):
    """lab + git repo + evallab.toml + the fixture dataset imported as drones@v1."""
    from evallab.datasets import import_dataset

    import shutil

    (lab.root / "evallab.toml").write_text(LAB_TOML)
    shutil.copy(FIXTURES.parent.parent / "pricing.yaml", lab.root / "pricing.yaml")
    import_dataset("drones", FIXTURES / "questions.jsonl", lab.root / "corpus", "fixture", lab)
    git(lab.root, "init", "-q")
    git(lab.root, "config", "user.email", "t@example.test")
    git(lab.root, "config", "user.name", "t")
    git(lab.root, "add", "-A")
    git(lab.root, "commit", "-qm", "init")
    return lab


@pytest.fixture
def write_experiment(git_lab):
    def _write(name: str, text: str, commit: bool = True) -> Path:
        path = git_lab.root / "experiments" / f"{name}.yaml"
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
        if commit:
            git(git_lab.root, "add", str(path))
            git(git_lab.root, "commit", "-qm", f"add {name}")
        return path

    return _write
