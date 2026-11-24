"""``qase-helper runs ...``: manage Qase test runs."""

import logging

import typer

from qase_helper.cli.common import EXIT_ERROR, get_settings, handle_errors
from qase_helper.client import QaseClient, QaseObjectKind
from qase_helper.errors import ConfigError, QaseApiError
from qase_helper.run_filter import RunFilter, parse_date

LOG = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True, help="Manage Qase test runs.")


@app.command("delete")
@handle_errors
def delete(
    ctx: typer.Context,
    since: str = typer.Option(None, "--since", metavar="YYYY-MM-DD", help="Runs started on or after this date (UTC)."),
    until: str = typer.Option(None, "--until", metavar="YYYY-MM-DD", help="Runs started on or before this date (UTC)."),
    milestone: str = typer.Option(None, "--milestone", help="Runs in this milestone (name or ID)."),
    environment: str = typer.Option(None, "--environment", help="Runs in this environment (name or ID)."),
    title_contains: list[str] = typer.Option(
        None, "--title-contains", help="Run title must contain this text. Repeatable; all must match."
    ),
    case_sensitive: bool = typer.Option(False, "--case-sensitive", help="Case-sensitive --title-contains matching."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Only list matching runs, never delete."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Delete the matching runs. Without it, runs are only listed."),
):
    """Delete test runs that match ALL given filters.

    At least one filter is required. Without --yes the matching runs are only listed.
    """
    settings = get_settings(ctx)
    settings.require_credentials()

    with QaseClient(settings.qase_token, settings.qase_project, settings.api_host) as client:
        run_filter = RunFilter(
            since=parse_date(since),
            until=parse_date(until),
            milestone_id=client.resolve_id(QaseObjectKind.MILESTONE, milestone),
            environment_id=client.resolve_id(QaseObjectKind.ENVIRONMENT, environment),
            title_contains=title_contains or [],
            case_sensitive=case_sensitive,
        )
        if run_filter.is_empty:
            raise ConfigError(
                "At least one filter is required (--since, --until, --milestone, --environment or --title-contains)."
            )

        runs = run_filter.apply(
            client.list_runs(
                milestone_id=run_filter.milestone_id,
                environment_id=run_filter.environment_id,
                from_start_time=run_filter.from_start_time,
                to_start_time=run_filter.to_start_time,
            )
        )

        typer.echo(f"{len(runs)} run(s) match in project {settings.qase_project}:")
        for run in runs:
            typer.echo(f"  [{run.id}] {run.title} (status={run.status_text}, started={run.start_time})")
        if not runs:
            return
        if dry_run or not yes:
            typer.echo("Dry run: nothing deleted." if dry_run else "Pass --yes to delete these runs.")
            return

        failed = []
        for run in runs:
            try:
                client.delete_run(run.id)
            except QaseApiError as exc:
                LOG.error("Failed to delete run %s: %s", run.id, exc)
                failed.append(run.id)

    typer.echo(f"Deleted {len(runs) - len(failed)} run(s), {len(failed)} failed.")
    if failed:
        raise typer.Exit(EXIT_ERROR)
