"""``qase-helper cases ...``: manage Qase test cases."""

import typer

from qase_helper.case_map import load_case_map
from qase_helper.cases import CaseCreateOptions, CaseCreator
from qase_helper.cli.common import (
    CaseIdMapOpt,
    ExcludeSkippedOpt,
    JunitReportArg,
    MaxLengthOpt,
    get_settings,
    handle_errors,
    pick,
)
from qase_helper.client import QaseClient
from qase_helper.junit import parse_junit

app = typer.Typer(no_args_is_help=True, help="Manage Qase test cases.")


@app.command("create")
@handle_errors
def create(
    ctx: typer.Context,
    junit_report: JunitReportArg,
    suite: str = typer.Option(None, "--suite", help="Create cases in this suite (name or ID). Default: project root."),
    case_id_map: CaseIdMapOpt = None,
    max_length: MaxLengthOpt = None,
    exclude_skipped: ExcludeSkippedOpt = None,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show which cases would be created, without creating them."),
):
    """Create a Qase test case for every test in a JUnit report that has no case yet.

    A test already has a case if its name is in the case-ID map or a case with
    exactly this title exists in the project. New cases are marked as automated.
    """
    settings = get_settings(ctx)
    case_map_path = pick(case_id_map, settings.case_id_map_file)
    options = CaseCreateOptions(
        suite=pick(suite, settings.suite),
        max_length=pick(max_length, settings.max_length),
        exclude_skipped=pick(exclude_skipped, settings.exclude_skipped),
        dry_run=dry_run,
    )

    results = parse_junit(junit_report)
    case_map = load_case_map(case_map_path) if case_map_path else {}

    settings.require_credentials()
    with QaseClient(settings.qase_token, settings.qase_project, settings.api_host) as client:
        summary = CaseCreator(client).create(results, case_map, options)

    plan = summary.plan
    location = f"suite {summary.suite_id}" if summary.suite_id is not None else "the project root"
    if dry_run:
        typer.echo(f"Dry run: {len(plan.to_create)} case(s) would be created in {location}:")
        for name in plan.to_create:
            typer.echo(f"  {name}")
    else:
        typer.echo(f"Created {len(summary.created)} case(s) in {location}:")
        for name, case_id in summary.created.items():
            typer.echo(f"  [{case_id}] {name}")

    excluded = f", {summary.excluded_count} skipped excluded" if summary.excluded_count else ""
    typer.echo(
        f"Project {settings.qase_project}: {len(plan.existing)} test(s) already have a case, "
        f"{len(plan.mapped)} are in the case-ID map{excluded}."
    )
