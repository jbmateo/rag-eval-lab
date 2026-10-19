import json
import shutil

import pytest
from typer.testing import CliRunner

from evallab.datasets import (
    DatasetError, Case, Expected, evidence_matches, import_dataset, load_dataset, new_draft, publish, subset,
    validate,
)
from tests.conftest import FIXTURES

SRC = FIXTURES / "questions.jsonl"


@pytest.fixture
def imported(lab):
    import_dataset("drones", SRC, lab.root / "corpus", "Initial fixture", lab)
    return lab


def test_import_creates_v1(imported):
    ds = load_dataset("drones@v1", imported)
    assert ds.version == "v1" and len(ds.cases) == 20
    manifest = (imported.root / "datasets/drones/manifest.yaml").read_text()
    assert "v1.jsonl" in manifest and "cases: 20" in manifest and "parent: null" in manifest
    assert ds.sha256 in manifest


def test_tampered_version_refused(imported):
    with open(imported.root / "datasets/drones/v1.jsonl", "a") as f:
        f.write(" ")
    with pytest.raises(DatasetError, match="sha256 mismatch"):
        load_dataset("drones@v1", imported)


def test_corpus_change_refused(imported):
    p = imported.root / "corpus/drones.md"
    p.write_text(p.read_text() + "\nNew line.\n")
    with pytest.raises(DatasetError, match="corpus lock"):
        load_dataset("drones@v1", imported)


def _case(**over):
    base = dict(id="x1", question="q?", answerable=True, tag="t",
                expected=[Expected(document="drones.md", evidence="The HD-4 battery lasts 38 minutes")])
    return Case(**{**base, **over})


@pytest.mark.parametrize("cases, needle", [
    ([_case(), _case()], "duplicate id"),
    ([_case(expected=[Expected(document="nope.md", evidence="x")])], "unknown document"),
    ([_case(expected=[Expected(document="drones.md", evidence="not in the text at all here")])], "evidence not found"),
    ([_case(answerable=False)], "unanswerable"),
])
def test_validate_catches(fixture_corpus, cases, needle):
    errors = validate(cases, fixture_corpus)
    assert len(errors) == 1 and needle in errors[0] and "x1" in errors[0]


def test_validate_accepts_fixture(fixture_corpus):
    cases = [Case(**json.loads(l)) for l in SRC.read_text().splitlines()]
    assert validate(cases, fixture_corpus) == []


def test_evidence_head_match():
    e = Expected(document="a.md", evidence="one two three four five six seven eight nine ten")
    assert evidence_matches("a.md", "...ONE two  three four five six seven eight", e)
    assert not evidence_matches("b.md", "one two three four five six seven eight nine ten", e)
    assert not evidence_matches("a.md", "one two three", e)


def test_new_and_publish_v2(imported):
    v1_bytes = (imported.root / "datasets/drones/v1.jsonl").read_bytes()
    draft = new_draft("drones", "v1", imported)
    lines = draft.read_text().splitlines()
    draft.write_text("\n".join(lines[:-1]) + "\n")
    with pytest.raises(DatasetError, match="changes"):
        publish("drones", "", imported)
    ds = publish("drones", "Drop f20", imported)
    assert ds.version == "v2" and len(ds.cases) == 19
    assert "parent: v1" in (imported.root / "datasets/drones/manifest.yaml").read_text()
    assert (imported.root / "datasets/drones/v1.jsonl").read_bytes() == v1_bytes
    assert not draft.exists()


def test_publish_rejects_invalid_draft(imported):
    draft = new_draft("drones", "v1", imported)
    draft.write_text(draft.read_text() + draft.read_text().splitlines()[0] + "\n")
    with pytest.raises(DatasetError, match="duplicate id"):
        publish("drones", "dup", imported)


def test_balanced_subset_stable(imported):
    ds = load_dataset("drones@v1", imported)
    a, b = subset(ds, "balanced-10"), subset(ds, "balanced-10")
    assert [c.id for c in a] == [c.id for c in b] and len(a) == 10
    counts = {}
    for c in a:
        counts[c.tag] = counts.get(c.tag, 0) + 1
    assert max(counts.values()) - min(counts.values()) <= 1
    with pytest.raises(ValueError):
        subset(ds, "balanced-99")


def test_unknown_version_message(imported):
    with pytest.raises(DatasetError) as e:
        load_dataset("drones@v9", imported)
    assert "v9" in str(e.value) and "available: v1" in str(e.value)
    with pytest.raises(DatasetError, match="available: drones"):
        load_dataset("nope@v1", imported)


def test_cli_missing_dataset_exit_code(imported, monkeypatch):
    from evallab.cli import app

    (imported.root / "evallab.toml").write_text(
        '[budget]\ntotal_usd = 1.0\n[judge]\nmodel = "fake"\nrubric_version = "v1"\n')
    monkeypatch.chdir(imported.root)
    r = CliRunner().invoke(app, ["dataset", "validate", "drones@v9"])
    assert r.exit_code == 2
    assert len(r.output.strip().splitlines()) == 1 and "v9" in r.output
