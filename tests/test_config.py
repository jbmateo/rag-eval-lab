from pathlib import Path

import pytest

from evallab.config import load_settings

TOML = """
[budget]
total_usd = 1.00

[judge]
model = "claude-haiku-5-5"
rubric_version = "v1"

[paths]
store = "results/evallab.db"
cache = "cache"
export = "dashboard/public/data"

[systems.rag_studio]
path = "../rag-studio/backend"
embedder = "fastembed"

[ci]
baseline_run = ""
"""


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / "evallab.toml").write_text(TOML)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return tmp_path


def test_loads_defaults(root):
    s = load_settings(root)
    assert s.budget_total_usd == 1.0
    assert s.judge_model == "claude-haiku-5-5" and s.judge_rubric_version == "v1"
    assert s.store_path == root / "results/evallab.db"
    assert s.cache_dir == root / "cache"
    assert s.export_dir == root / "dashboard/public/data"
    assert s.systems["rag_studio"]["embedder"] == "fastembed"
    assert s.ci_baseline_run == ""


def test_finds_root_from_subdirectory(root, monkeypatch):
    sub = root / "a" / "b"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    assert load_settings().root == root


def test_api_key_from_env_over_dotenv(root, monkeypatch):
    (root / ".env").write_text("ANTHROPIC_API_KEY=from-dotenv\n")
    assert load_settings(root).anthropic_api_key == "from-dotenv"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    assert load_settings(root).anthropic_api_key == "from-env"


def test_api_key_never_read_from_toml(root):
    (root / "evallab.toml").write_text(TOML + '\n[secrets]\nanthropic_api_key = "nope"\n')
    assert load_settings(root).anthropic_api_key == ""


def test_missing_toml_is_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="evallab.toml"):
        load_settings(tmp_path)
