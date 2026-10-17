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
