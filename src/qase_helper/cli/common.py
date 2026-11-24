"""Helpers shared by CLI commands."""

import functools
import logging

import typer

from qase_helper.config import Settings
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
