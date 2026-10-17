"""Versioned evaluation datasets: immutable JSONL versions, a manifest, and a corpus lock."""
import datetime as dt
import hashlib
import json
import os
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from evallab.adapters.base import Corpus
from evallab.config import Settings
from evallab.stats import Mulberry32

HEAD_WORDS = 8


class DatasetError(Exception):
    """User-facing dataset problem; the message is shown as is."""


class Expected(BaseModel, extra="forbid"):
    document: str
    evidence: str


class Case(BaseModel, extra="forbid"):
    id: str
    question: str
    answerable: bool
    tag: str
    expected: list[Expected]
    reference_answer: str | None = None


@dataclass
class Dataset:
    name: str
    version: str
    sha256: str
    cases: list[Case]
    corpus: Corpus

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"


def norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def evidence_matches(chunk_document: str, chunk_text: str, e: Expected) -> bool:
    if chunk_document != e.document:
        return False
    text, ev = norm(chunk_text), norm(e.evidence)
    return ev in text or " ".join(ev.split()[:HEAD_WORDS]) in text


# --- document text ----------------------------------------------------------------------------------


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    if suffix == ".docx":
        import docx

        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    raw = path.read_bytes().decode("utf-8-sig", errors="replace")
    if suffix in (".html", ".htm"):
        parser = _TextOnly()
        parser.feed(raw)
        return " ".join(parser.parts)
    return raw


# --- validation -------------------------------------------------------------------------------------


def validate(cases: list[Case], corpus: Corpus) -> list[str]:
    errors: list[str] = []
    files = {p.name: p for p in corpus.files}
    texts: dict[str, str] = {}
    seen: set[str] = set()
    for c in cases:
        if c.id in seen:
            errors.append(f"{c.id}: duplicate id")
            continue
        seen.add(c.id)
        if not c.tag.strip():
            errors.append(f"{c.id}: empty tag")
        if not c.answerable:
            if c.expected:
                errors.append(f"{c.id}: unanswerable case has expected evidence")
            continue
        if not c.expected:
            errors.append(f"{c.id}: answerable case has no expected evidence")
        for e in c.expected:
            if e.document not in files:
                errors.append(f"{c.id}: unknown document {e.document!r}")
                continue
            if e.document not in texts:
                texts[e.document] = norm(document_text(files[e.document]))
            if norm(e.evidence) not in texts[e.document]:
                errors.append(f"{c.id}: evidence not found in {e.document}: {e.evidence[:60]!r}")
    return errors


# --- files ------------------------------------------------------------------------------------------


def _dataset_dir(name: str, settings: Settings) -> Path:
    return settings.root / "datasets" / name


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lock_lines(corpus_path: Path) -> str:
    files = sorted(p for p in corpus_path.iterdir() if p.is_file() and not p.name.startswith("."))
    return "".join(f"{_sha256(p)}  {p.name}\n" for p in files)


def _read_cases(path: Path) -> list[Case]:
    cases = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(Case.model_validate_json(line))
        except ValidationError as e:
            raise DatasetError(f"{path.name} line {n}: {e.errors()[0]['msg']}") from e
    return cases


def _write_cases(path: Path, cases: list[Case]) -> None:
    path.write_text("".join(c.model_dump_json() + "\n" for c in cases), encoding="utf-8")


def _load_manifest(name: str, settings: Settings) -> dict:
    path = _dataset_dir(name, settings) / "manifest.yaml"
    if not path.exists():
        root = settings.root / "datasets"
        known = sorted(p.name for p in root.iterdir() if (p / "manifest.yaml").exists()) if root.exists() else []
        raise DatasetError(f"Unknown dataset {name!r}; available: {', '.join(known) or 'none'}")
    return yaml.safe_load(path.read_text())


def _save_manifest(name: str, manifest: dict, settings: Settings) -> None:
    path = _dataset_dir(name, settings) / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))


def _corpus(name: str, manifest: dict, settings: Settings, check: bool = True) -> Corpus:
    ddir = _dataset_dir(name, settings)
    corpus_path = (settings.root / manifest["corpus"]["path"]).resolve()
    lock_path = ddir / manifest["corpus"]["lock"]
    if check and _lock_lines(corpus_path) != lock_path.read_text():
        raise DatasetError(f"{name}: corpus lock mismatch — files in {corpus_path} changed since the dataset was locked")
    files = [corpus_path / line.split("  ", 1)[1] for line in lock_path.read_text().splitlines()]
    return Corpus(name=name, path=corpus_path, lock_hash=_sha256(lock_path), files=files)


def parse_ref(ref: str) -> tuple[str, str]:
    name, sep, version = ref.partition("@")
    if not sep or not name or not version:
        raise DatasetError(f"Dataset reference {ref!r} must look like name@version, e.g. lumen@v1")
    return name, version


def load_dataset(ref: str, settings: Settings) -> Dataset:
    name, version = parse_ref(ref)
    manifest = _load_manifest(name, settings)
    entry = next((v for v in manifest["versions"] if v["version"] == version), None)
    if entry is None:
        known = ", ".join(v["version"] for v in manifest["versions"])
        raise DatasetError(f"{name} has no version {version!r}; available: {known}")
    path = _dataset_dir(name, settings) / entry["file"]
    sha = _sha256(path)
    if sha != entry["sha256"]:
        raise DatasetError(f"{ref}: sha256 mismatch — {entry['file']} was modified after publishing")
    corpus = _corpus(name, manifest, settings)
    cases = _read_cases(path)
    errors = validate(cases, corpus)
    if errors:
        raise DatasetError(f"{ref} is invalid: " + "; ".join(errors))
    return Dataset(name=name, version=version, sha256=sha, cases=cases, corpus=corpus)


def import_dataset(name: str, source_jsonl: Path, corpus_path: Path, changes: str, settings: Settings) -> Dataset:
    ddir = _dataset_dir(name, settings)
    if (ddir / "manifest.yaml").exists():
        raise DatasetError(f"Dataset {name!r} already exists; use `evallab dataset new` for a new version")
    if not changes.strip():
        raise DatasetError("A --changes message is required")
    corpus_path = Path(corpus_path).resolve()
    ddir.mkdir(parents=True)
    (ddir / "corpus.lock").write_text(_lock_lines(corpus_path))
    manifest = {"name": name,
                "corpus": {"path": os.path.relpath(corpus_path, settings.root), "lock": "corpus.lock"},
                "versions": []}
    cases = _read_cases(Path(source_jsonl))
    errors = validate(cases, _corpus(name, manifest, settings, check=False))
    if errors:
        raise DatasetError(f"{source_jsonl} is invalid: " + "; ".join(errors))
    _write_cases(ddir / "v1.jsonl", cases)
    _append_version(name, manifest, "v1", None, len(cases), changes, settings)
    return load_dataset(f"{name}@v1", settings)


def _append_version(name, manifest, version, parent, n, changes, settings) -> None:
    file = f"{version}.jsonl"
    manifest["versions"].append({
        "version": version, "file": file, "sha256": _sha256(_dataset_dir(name, settings) / file),
        "cases": n, "created": dt.date.today().isoformat(), "parent": parent, "changes": changes,
    })
    _save_manifest(name, manifest, settings)


def new_draft(name: str, from_version: str, settings: Settings) -> Path:
    ds = load_dataset(f"{name}@{from_version}", settings)
    draft = _dataset_dir(name, settings) / "draft.jsonl"
    if draft.exists():
        raise DatasetError(f"{draft} already exists; publish or delete it first")
    _write_cases(draft, ds.cases)
    (_dataset_dir(name, settings) / "draft.parent").write_text(from_version)
    return draft


def publish(name: str, changes: str, settings: Settings) -> Dataset:
    ddir = _dataset_dir(name, settings)
    draft = ddir / "draft.jsonl"
    if not draft.exists():
        raise DatasetError(f"No draft for {name}; run `evallab dataset new {name} --from <version>` first")
    if not changes.strip():
        raise DatasetError("A --changes message is required")
    manifest = _load_manifest(name, settings)
    cases = _read_cases(draft)
    errors = validate(cases, _corpus(name, manifest, settings))
    if errors:
        raise DatasetError(f"draft is invalid: " + "; ".join(errors))
    numbers = [int(re.sub(r"\D", "", v["version"])) for v in manifest["versions"]]
    version = f"v{max(numbers) + 1}"
    draft.rename(ddir / f"{version}.jsonl")
    parent_file = ddir / "draft.parent"
    parent = parent_file.read_text().strip()
    parent_file.unlink()
    _append_version(name, manifest, version, parent, len(cases), changes, settings)
    return load_dataset(f"{name}@{version}", settings)


def list_datasets(settings: Settings) -> list[dict]:
    root = settings.root / "datasets"
    if not root.exists():
        return []
    return [yaml.safe_load((p / "manifest.yaml").read_text()) for p in sorted(root.iterdir())
            if (p / "manifest.yaml").exists()]


# --- subsets ----------------------------------------------------------------------------------------


def subset(ds: Dataset, spec: str | None) -> list[Case]:
    if spec is None:
        return list(ds.cases)
    m = re.fullmatch(r"balanced-(\d+)", spec)
    if not m:
        raise DatasetError(f"Unknown subset {spec!r}; supported: balanced-<n>")
    n = int(m.group(1))
    if n > len(ds.cases) or n < 1:
        raise ValueError(f"subset {spec}: n must be between 1 and {len(ds.cases)}")
    by_tag: dict[str, list[Case]] = {}
    for c in sorted(ds.cases, key=lambda c: c.id):
        by_tag.setdefault(c.tag, []).append(c)
    rng = Mulberry32(0)
    queues = {tag: rng.shuffle(cases) for tag, cases in sorted(by_tag.items())}
    picked: list[Case] = []
    while len(picked) < n:
        for tag in sorted(queues):
            if queues[tag] and len(picked) < n:
                picked.append(queues[tag].pop(0))
    return picked
