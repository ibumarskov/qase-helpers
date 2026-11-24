"""Report JUnit results to Qase: validate names, resolve IDs, create/complete the run, submit results."""

import logging
from dataclasses import dataclass

from qase_helper.case_map import resolve_case_ids, validate_names
from qase_helper.client import QaseClient, QaseObjectKind, to_result_create
from qase_helper.config import DEFAULT_MAX_LENGTH, DEFAULT_RUN_TITLE
from qase_helper.errors import ConfigError
from qase_helper.junit import TestResult, select_results

LOG = logging.getLogger(__name__)

MAX_RUN_DESCRIPTION_LENGTH = 10000  # Qase API limit for a run description


@dataclass(frozen=True)
class ReportOptions:
    """What to report into. ``milestone``/``environment``/``plan`` accept a name or a numeric ID."""

    run_id: int | None = None
    run_title: str = DEFAULT_RUN_TITLE
    run_description: str | None = None
    milestone: str | None = None
    environment: str | None = None
    plan: str | None = None
    complete_run: bool = True
    max_length: int = DEFAULT_MAX_LENGTH
    exclude_skipped: bool = False


@dataclass(frozen=True)
class ReportPlan:
    """Everything resolved before the run is touched: what will be sent and where."""

    results: list[TestResult]
    case_ids: dict[str, int]  # test name -> Qase case ID
    excluded_count: int = 0
    milestone_id: int | None = None
    environment_id: int | None = None
    plan_id: int | None = None


@dataclass(frozen=True)
class ReportSummary:
    run_id: int
    run_created: bool
    run_completed: bool
    results_count: int
    excluded_count: int = 0


class Reporter:
    """Submits parsed JUnit results to a Qase test run."""

    def __init__(self, client: QaseClient):
        self._client = client

    def prepare(
        self,
        results: list[TestResult],
        case_map: dict[str, int] | None = None,
        options: ReportOptions | None = None,
    ) -> ReportPlan:
        """Validate the results and resolve every Qase ID they need, using read-only API calls.

        Every test must match exactly one case: through the case-ID map, or by an exact
        case title. Qase projects may refuse results without a case ID, and results
        submitted by title would create duplicate cases, so nothing is sent by title.
        """
        case_map = case_map or {}
        options = options or ReportOptions()
        if options.run_description and len(options.run_description) > MAX_RUN_DESCRIPTION_LENGTH:
            raise ConfigError(
                f"Run description is {len(options.run_description)} characters long; "
                f"Qase allows at most {MAX_RUN_DESCRIPTION_LENGTH}."
            )
        selected = select_results(results, options.exclude_skipped)
        excluded_count = len(results) - len(selected)
        if excluded_count:
            LOG.info("Excluded %d skipped result(s).", excluded_count)

        names = [result.name for result in selected]
        validate_names(names, case_map, options.max_length)  # offline check first, no API call
        needs_lookup = any(name not in case_map for name in names)
        ids_by_title = self._client.list_case_ids_by_title() if needs_lookup else {}
        case_ids = resolve_case_ids(names, case_map, ids_by_title)

        milestone_id = environment_id = plan_id = None
        if options.run_id is None:  # milestone/environment/plan only apply to a new run
            milestone_id = self._client.resolve_id(QaseObjectKind.MILESTONE, options.milestone)
            environment_id = self._client.resolve_id(QaseObjectKind.ENVIRONMENT, options.environment)
            plan_id = self._client.resolve_id(QaseObjectKind.PLAN, options.plan)
        return ReportPlan(
            results=selected,
            case_ids=case_ids,
            excluded_count=excluded_count,
            milestone_id=milestone_id,
            environment_id=environment_id,
            plan_id=plan_id,
        )

    def report(
        self,
        results: list[TestResult],
        case_map: dict[str, int] | None = None,
        options: ReportOptions | None = None,
    ) -> ReportSummary:
        options = options or ReportOptions()
        # Resolve everything before creating the run, so a bad report never leaves an empty run behind.
        plan = self.prepare(results, case_map, options)
        payload = [to_result_create(result, plan.case_ids[result.name]) for result in plan.results]

        run_id = options.run_id
        run_created = run_id is None
        if run_created:
            run_id = self._client.create_run(
                options.run_title,
                description=options.run_description or None,
                milestone_id=plan.milestone_id,
                environment_id=plan.environment_id,
                plan_id=plan.plan_id,
            )
            LOG.info("Created run %s.", run_id)
        else:
            LOG.info("Reporting into existing run %s.", run_id)

        self._client.submit_results(run_id, payload)
        LOG.info("Submitted %d result(s) to run %s.", len(payload), run_id)

        # An existing run is owned by whoever created it; only complete runs created here.
        run_completed = run_created and options.complete_run
        if run_completed:
            self._client.complete_run(run_id)
            LOG.info("Completed run %s.", run_id)

        return ReportSummary(
            run_id=run_id,
            run_created=run_created,
            run_completed=run_completed,
            results_count=len(payload),
            excluded_count=plan.excluded_count,
        )
