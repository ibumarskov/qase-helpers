"""``qase-helper report``: submit JUnit results to Qase."""

import typer

from qase_helper.case_map import load_case_map
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
from qase_helper.reporter import Reporter, ReportOptions


@handle_errors
def report(
    ctx: typer.Context,
    junit_report: JunitReportArg,
    run_id: int = typer.Option(None, "--run-id", help="Report into this existing run instead of creating one."),
    run_title: str = typer.Option(None, "--run-title", show_default="Automated run", help="Title of the new run."),
    run_description: str = typer.Option(
        None, "--run-description", help="Description of the new run (up to 10000 characters)."
    ),
    milestone: str = typer.Option(None, "--milestone", help="Milestone of the new run (name or ID)."),
    environment: str = typer.Option(None, "--environment", help="Environment of the new run (name or ID)."),
    plan: str = typer.Option(None, "--plan", help="Test plan of the new run (name or ID)."),
    case_id_map: CaseIdMapOpt = None,
    max_length: MaxLengthOpt = None,
    complete: bool = typer.Option(
        None,
        "--complete/--no-complete",
        show_default="complete",
        help="Complete the run after reporting (only runs created by this command).",
    ),
    exclude_skipped: ExcludeSkippedOpt = None,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate the report and resolve case IDs (read-only API calls) without creating a run.",
    ),
):
    """Submit the results of a JUnit XML report to a Qase test run.

    Every test is matched to a Qase case: through the case-ID map, or by an exact
    case title. Tests without exactly one matching case fail the command before a
    run is created; create missing cases with `qase-helper cases create`.
    """
    settings = get_settings(ctx)
    case_map_path = pick(case_id_map, settings.case_id_map_file)
    options = ReportOptions(
        run_id=pick(run_id, settings.run_id),
        run_title=pick(run_title, settings.run_title),
        run_description=pick(run_description, settings.run_description),
        milestone=pick(milestone, settings.milestone),
        environment=pick(environment, settings.environment),
        plan=pick(plan, settings.plan),
        complete_run=pick(complete, settings.complete_run),
        max_length=pick(max_length, settings.max_length),
        exclude_skipped=pick(exclude_skipped, settings.exclude_skipped),
    )

    results = parse_junit(junit_report)
    case_map = load_case_map(case_map_path) if case_map_path else {}

    settings.require_credentials()
    with QaseClient(settings.qase_token, settings.qase_project, settings.api_host) as client:
        reporter = Reporter(client)
        if dry_run:
            plan = reporter.prepare(results, case_map, options)
        else:
            summary = reporter.report(results, case_map, options)

    if dry_run:
        target = f"existing run {options.run_id}" if options.run_id is not None else f"new run {options.run_title!r}"
        excluded_note = f" ({plan.excluded_count} skipped excluded)" if plan.excluded_count else ""
        typer.echo(f"Dry run: {len(plan.results)} result(s) would be reported to {target}{excluded_note}.")
        for result in plan.results:
            source = "map" if result.name in case_map else "title"
            typer.echo(
                f"  {result.status.value:<8} case_id={plan.case_ids[result.name]:<7} ({source:<5}) {result.name}"
            )
        return

    action = "created" if summary.run_created else "updated"
    completed = ", completed" if summary.run_completed else ""
    excluded = f", {summary.excluded_count} skipped excluded" if summary.excluded_count else ""
    typer.echo(
        f"Reported {summary.results_count} result(s) to run {summary.run_id} "
        f"in project {settings.qase_project} ({action}{completed}{excluded})."
    )
    run_url = settings.run_url(summary.run_id)
    if run_url:
        typer.echo(f"Run URL: {run_url}")
