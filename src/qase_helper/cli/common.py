"""Helpers shared by CLI commands."""

import functools
import logging
from pathlib import Path
from typing import Annotated

import typer

from qase_helper.config import DEFAULT_MAX_LENGTH, Settings
from qase_helper.errors import QaseHelperError

LOG = logging.getLogger("qase_helper")

EXIT_ERROR = 1


def handle_errors(func):
    """Turn QaseHelperError into a logged error message and exit code 1 (no traceback)."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except QaseHelperError as exc:
            LOG.error("%s", exc)
            LOG.debug("Error details:", exc_info=True)
            raise typer.Exit(EXIT_ERROR) from exc

    return wrapper


def get_settings(ctx: typer.Context) -> Settings:
    return ctx.find_root().obj


def pick(cli_value, settings_value):
    """CLI value if the option was given, otherwise the value from env/config/defaults."""
    return cli_value if cli_value is not None else settings_value


# Options shared by commands that map JUnit tests to Qase cases (report, cases create).
JunitReportArg = Annotated[Path, typer.Argument(help="Path to the JUnit XML report.", show_default=False)]
CaseIdMapOpt = Annotated[
    Path | None, typer.Option("--case-id-map", help="YAML file mapping full test names to Qase case IDs.")
]
MaxLengthOpt = Annotated[
    int | None,
    typer.Option(
        "--max-length",
        min=1,
        max=DEFAULT_MAX_LENGTH,
        show_default=str(DEFAULT_MAX_LENGTH),
        help="Max test name length; longer names must be in the case-ID map.",
    ),
]
ExcludeSkippedOpt = Annotated[
    bool | None,
    typer.Option("--exclude-skipped/--include-skipped", show_default="include", help="Ignore skipped tests."),
]
