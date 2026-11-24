"""Report JUnit results to Qase: validate names, resolve IDs, create/complete the run, submit results."""

import logging
from dataclasses import dataclass

from qase_helper.client import QaseClient, QaseObjectKind, to_result_create
from qase_helper.config import DEFAULT_MAX_LENGTH, DEFAULT_RUN_TITLE
from qase_helper.errors import TestNameTooLongError
from qase_helper.junit import TestResult, TestStatus

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportOptions:
    """What to report into. ``milestone``/``environment``/``plan`` accept a name or a numeric ID."""

    run_id: int | None = None
    run_title: str = DEFAULT_RUN_TITLE
    milestone: str | None = None
    environment: str | None = None
    plan: str | None = None
    complete_run: bool = True
    max_length: int = DEFAULT_MAX_LENGTH
    exclude_skipped: bool = False


@dataclass(frozen=True)
class ReportSummary:
    run_id: int
    run_created: bool
    run_completed: bool
    results_count: int
    excluded_count: int = 0


def select_results(results: list[TestResult], exclude_skipped: bool) -> list[TestResult]:
    """Return the results to report: all of them, or all except skipped ones."""
    if not exclude_skipped:
        return list(results)
    return [result for result in results if result.status is not TestStatus.SKIPPED]


def validate_names(results: list[TestResult], case_map: dict[str, int], max_length: int) -> None:
    """Raise TestNameTooLongError for every name longer than ``max_length`` that is not in ``case_map``."""
    too_long = [result.name for result in results if len(result.name) > max_length and result.name not in case_map]
    if too_long:
        raise TestNameTooLongError(list(dict.fromkeys(too_long)), max_length)


class Reporter:
    """Submits parsed JUnit results to a Qase test run."""

    def __init__(self, client: QaseClient):
        self._client = client

    def report(
        self,
        results: list[TestResult],
        case_map: dict[str, int] | None = None,
        options: ReportOptions | None = None,
    ) -> ReportSummary:
        case_map = case_map or {}
        options = options or ReportOptions()
        selected = select_results(results, options.exclude_skipped)
        excluded_count = len(results) - len(selected)
        if excluded_count:
            LOG.info("Excluded %d skipped result(s).", excluded_count)
        results = selected

        # Validate before any API call, so a bad report never leaves a half-filled run behind.
        validate_names(results, case_map, options.max_length)
        payload = [to_result_create(result, case_map.get(result.name)) for result in results]

        run_id = options.run_id
        run_created = run_id is None
        if run_created:
            run_id = self._client.create_run(
                options.run_title,
                milestone_id=self._client.resolve_id(QaseObjectKind.MILESTONE, options.milestone),
                environment_id=self._client.resolve_id(QaseObjectKind.ENVIRONMENT, options.environment),
                plan_id=self._client.resolve_id(QaseObjectKind.PLAN, options.plan),
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
            excluded_count=excluded_count,
        )
