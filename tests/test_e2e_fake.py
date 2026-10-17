import json
import shutil

import pytest
from typer.testing import CliRunner

from evallab.cli import app
from tests.conftest import FIXTURES, git


def test_run_compare_export_e2e(git_lab, monkeypatch):
    exp = git_lab.root / "experiments" / "fake-sweep.yaml"
    exp.parent.mkdir()
    shutil.copy(FIXTURES / "experiments" / "fake-sweep.yaml", exp)
    git(git_lab.root, "add", "-A")
    git(git_lab.root, "commit", "-qm", "experiment")
    monkeypatch.chdir(git_lab.root)
    cli = CliRunner()

    r = cli.invoke(app, ["run", "experiments/fake-sweep.yaml", "--yes"])
    assert r.exit_code == 0, r.output
    assert "quality=0.4: complete" in r.output and "quality=0.9: complete" in r.output

    r = cli.invoke(app, ["compare", "fake-sweep:quality=0.4", "fake-sweep:quality=0.9", "--format", "json"])
    assert r.exit_code == 0, r.output
    report = json.loads(r.output)
    assert report["counts"]["improved"] > 0 and report["n_compared"] == 20
    assert all(c["question"] for c in report["cases"])

    md = cli.invoke(app, ["compare", "fake-sweep:quality=0.4", "fake-sweep:quality=0.9",
                          "--out", "reports/fake.md"])
    assert md.exit_code == 0 and (git_lab.root / "reports/fake.md").read_text().startswith("# Compare")

    pytest.skip("export arrives in Task 14")
    r = cli.invoke(app, ["export"])
    assert r.exit_code == 0, r.output
    index = json.loads((git_lab.export_dir / "index.json").read_text())
    assert [e["name"] for e in index["experiments"]] == ["fake-sweep"]
    assert len(index["experiments"][0]["runs"]) == 2
