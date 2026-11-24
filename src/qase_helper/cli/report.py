"""``qase-helper report``: submit JUnit results to Qase."""

from pathlib import Path

import typer

from qase_helper.case_map import load_case_map
from qase_helper.cli.common import get_settings, handle_errors
from qase_helper.client import QaseClient
from qase_helper.junit import parse_junit
from qase_helper.reporter import Reporter, ReportOptions, validate_names


def _pick(cli_value, settings_value):
    return cli_value if cli_value is not None else settings_value


@handle_errors
def report(
    ctx: typer.Context,
    junit_report: Path = typer.Argument(..., help="Path to the JUnit XML report.", show_default=False),
    run_id: int = typer.Option(None, "--run-id", help="Report into this existing run instead of creating one."),
    run_title: str = typer.Option(None, "--run-title", show_default="Automated run", help="Title of the new run."),
    milestone: str = typer.Option(None, "--milestone", help="Milestone of the new run (name or ID)."),
    environment: str = typer.Option(None, "--environment", help="Environment of the new run (name or ID)."),
    plan: str = typer.Option(None, "--plan", help="Test plan of the new run (name or ID)."),
    case_id_map: Path = typer.Option(None, "--case-id-map", help="YAML file mapping full test names to Qase case IDs."),
    max_length: int = typer.Option(
        None,
        "--max-length",
        min=1,
        show_default="255",
        help="Max test name length; longer names must be in the case-ID map.",
    ),
    complete: bool = typer.Option(
        None,
        "--complete/--no-complete",
        show_default="complete",
        help="Complete the run after reporting (only runs created by this command).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Parse and validate the report without calling the Qase API."
    ),
):
    """Submit the results of a JUnit XML report to a Qase test run."""
    settings = get_settings(ctx)
    case_map_path = _pick(case_id_map, settings.case_id_map_file)
    options = ReportOptions(
        run_id=_pick(run_id, settings.run_id),
        run_title=_pick(run_title, settings.run_title),
        milestone=_pick(milestone, settings.milestone),
        environment=_pick(environment, settings.environment),
        plan=_pick(plan, settings.plan),
        complete_run=_pick(complete, settings.complete_run),
        max_length=_pick(max_length, settings.max_length),
    )

    results = parse_junit(junit_report)
    case_map = load_case_map(case_map_path) if case_map_path else {}

    if dry_run:
        validate_names(results, case_map, options.max_length)
        target = f"existing run {options.run_id}" if options.run_id is not None else f"new run {options.run_title!r}"
        typer.echo(f"Dry run: {len(results)} result(s) would be reported to {target}.")
        for result in results:
            case_id = case_map.get(result.name)
            ref = f"case_id={case_id}" if case_id is not None else "by title"
            typer.echo(f"  {result.status.value:<8} {ref:<16} {result.name}")
        return

    settings.require_credentials()
    with QaseClient(settings.qase_token, settings.qase_project, settings.api_host) as client:
        summary = Reporter(client).report(results, case_map, options)

    action = "created" if summary.run_created else "updated"
    completed = ", completed" if summary.run_completed else ""
    typer.echo(
        f"Reported {summary.results_count} result(s) to run {summary.run_id} "
        f"in project {settings.qase_project} ({action}{completed})."
    )
