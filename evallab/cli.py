"""`evallab` command line. Commands are thin wrappers over the library modules."""
from pathlib import Path

import typer

from evallab import __version__
from evallab.config import load_settings

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Evaluate and regression-test RAG systems.")
dataset_app = typer.Typer(no_args_is_help=True, help="Create, version and validate datasets.")
app.add_typer(dataset_app, name="dataset")


class UserError(Exception):
    """Raised for problems the user can fix; printed as one line, exit code 2."""


def fail(message: str, code: int = 2) -> None:
    typer.echo(message.splitlines()[0] if message else "error", err=True)
    raise typer.Exit(code)


def run_guarded(fn):
    """Map user-facing errors from the library to a one-line message and exit code 2."""
    from evallab.datasets import DatasetError

    try:
        return fn()
    except (DatasetError, UserError, FileNotFoundError, KeyError, ValueError) as e:
        fail(str(e).strip("'\""))


@app.callback()
def main() -> None:
    """Evaluate and regression-test RAG systems."""


@app.command()
def version() -> None:
    """Print the evallab version."""
    typer.echo(__version__)


@dataset_app.command("import")
def dataset_import(
    name: str,
    source: Path = typer.Option(..., "--from", help="Source JSONL file"),
    corpus: Path = typer.Option(..., "--corpus", help="Directory of corpus documents"),
    changes: str = typer.Option(..., "--changes", help="Changelog line for v1"),
) -> None:
    """Import a JSONL question file as version v1 of a new dataset."""
    from evallab.datasets import import_dataset

    ds = run_guarded(lambda: import_dataset(name, source, corpus, changes, load_settings()))
    typer.echo(f"{ds.ref}: {len(ds.cases)} cases, valid")


@dataset_app.command("validate")
def dataset_validate(ref: str) -> None:
    """Verify hashes, corpus lock and case validity of NAME@VERSION."""
    from evallab.datasets import load_dataset

    ds = run_guarded(lambda: load_dataset(ref, load_settings()))
    typer.echo(f"{ds.ref}: {len(ds.cases)} cases, valid")


@dataset_app.command("new")
def dataset_new(name: str, from_version: str = typer.Option(..., "--from")) -> None:
    """Start an editable draft from an existing version."""
    from evallab.datasets import new_draft

    path = run_guarded(lambda: new_draft(name, from_version, load_settings()))
    typer.echo(f"Draft written to {path}; edit it, then run `evallab dataset publish {name} --changes ...`")


@dataset_app.command("publish")
def dataset_publish(name: str, changes: str = typer.Option(..., "--changes")) -> None:
    """Validate the draft and publish it as the next version."""
    from evallab.datasets import publish

    ds = run_guarded(lambda: publish(name, changes, load_settings()))
    typer.echo(f"Published {ds.ref}: {len(ds.cases)} cases")


@dataset_app.command("list")
def dataset_list() -> None:
    """List datasets and their versions."""
    from evallab.datasets import list_datasets

    for m in list_datasets(load_settings()):
        for v in m["versions"]:
            typer.echo(f"{m['name']}@{v['version']}  {v['cases']} cases  {v['created']}  {v['changes']}")
