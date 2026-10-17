"""`evallab` command line. Commands are thin wrappers over the library modules."""
import typer

from evallab import __version__

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Evaluate and regression-test RAG systems.")


@app.command()
def version() -> None:
    """Print the evallab version."""
    typer.echo(__version__)


@app.callback()
def main() -> None:
    """Evaluate and regression-test RAG systems."""
