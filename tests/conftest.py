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
