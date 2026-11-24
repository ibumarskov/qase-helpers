"""Entry point of the ``qase-helper`` CLI."""

import logging
import sys

import typer

from qase_helper import __version__
from qase_helper.cli import report as report_cmd
from qase_helper.cli import runs as runs_cmd
from qase_helper.cli.common import handle_errors
from qase_helper.config import CONFIG_ENV_VAR, load_settings

app = typer.Typer(
    name="qase-helper",
    no_args_is_help=True,
    help="Report JUnit test results to Qase and manage Qase test runs.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.command("report")(report_cmd.report)
app.add_typer(runs_cmd.app, name="runs")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"qase-helper {__version__}")
        raise typer.Exit()


def _resolve_log_level(explicit_level: str | None, verbosity: int, fallback: str) -> str:
    if explicit_level:
        return explicit_level.upper()
    if verbosity >= 2:
        return "DEBUG"
    if verbosity == 1:
        return "INFO"
    return fallback.upper()


def configure_logging(level: str, log_file: str | None) -> None:
    """Log to stderr (stdout is reserved for command output) and optionally to a file."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    handlers[0].setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
        handlers.append(file_handler)
    logging.basicConfig(level=level, handlers=handlers, force=True)


@app.callback()
@handle_errors
def main(
    ctx: typer.Context,
    config: str = typer.Option(None, "--config", "-c", envvar=CONFIG_ENV_VAR, help="Path to the YAML config file."),
    token: str = typer.Option(None, "--token", help="Qase API token (prefer the QASE_HELPER_TOKEN env var)."),
    project: str = typer.Option(None, "--project", "-p", help="Qase project code."),
    api_host: str = typer.Option(None, "--api-host", help="Qase API URL, e.g. https://api.qase.io/v1."),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity (-v INFO, -vv DEBUG)."),
    log_level: str = typer.Option(None, "--log-level", help="Log level (overrides -v)."),
    log_file: str = typer.Option(None, "--log-file", help="Also write logs to this file."),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show the version and exit."
    ),
):
    """Report JUnit test results to Qase and manage Qase test runs."""
    # Configure stderr logging first so that config errors are visible.
    configure_logging("WARNING", None)
    settings = load_settings(
        config_file=config, qase_token=token, qase_project=project, api_host=api_host, log_file=log_file
    )
    settings = settings.model_copy(update={"log_level": _resolve_log_level(log_level, verbose, settings.log_level)})
    try:
        configure_logging(settings.log_level, settings.log_file)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    ctx.obj = settings
