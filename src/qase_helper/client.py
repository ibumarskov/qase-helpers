"""Thin wrapper over the Qase API v1 SDK (``qase.api_client_v1``).

This is the only module that talks to the Qase SDK. SDK exceptions are
wrapped in :class:`QaseApiError`.
"""

import functools
import logging
from collections.abc import Callable, Iterable
from enum import Enum

import qase.api_client_v1 as qc
from qase.api_client_v1.exceptions import ApiException

from qase_helper.errors import QaseApiError, QaseObjectNotFoundError
from qase_helper.junit import TestResult

LOG = logging.getLogger(__name__)

RESULT_BULK_MAX = 2000  # max results per ResultCreateBulk request
PAGE_SIZE = 100  # max `limit` accepted by the list endpoints


class QaseObjectKind(str, Enum):
    """Qase objects that can be referenced by name or ID."""

    MILESTONE = "milestone"
    ENVIRONMENT = "environment"
    PLAN = "plan"


def _api_call(operation: str):
    """Decorator: wrap SDK ApiException into QaseApiError."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ApiException as exc:
                raise QaseApiError(operation, status=exc.status, reason=exc.reason, body=exc.body) from exc

        return wrapper

    return decorator


def _paginate(fetch_page: Callable[[int, int], object]) -> Iterable:
    """Yield entities from a paginated list endpoint ``fetch_page(limit, offset)``."""
    offset = 0
    while True:
        page = fetch_page(PAGE_SIZE, offset).result.entities or []
        yield from page
        if len(page) < PAGE_SIZE:
            return
        offset += PAGE_SIZE


def to_result_create(result: TestResult, case_id: int | None = None) -> qc.ResultCreate:
    """Convert a TestResult into an SDK ResultCreate, targeting ``case_id`` or the case title."""
    return qc.ResultCreate(
        case_id=case_id,
        case=None if case_id is not None else qc.ResultCreateCase(title=result.name),
        status=result.status.value,
        time_ms=int(result.duration * 1000),
        stacktrace=result.stacktrace,
    )


class QaseClient:
    """Qase API v1 client scoped to one project. Use as a context manager or call :meth:`close`."""

    def __init__(self, token: str, project: str, api_host: str | None = None):
        configuration = qc.Configuration(host=api_host) if api_host else qc.Configuration()
        configuration.api_key["TokenAuth"] = token
        self.project = project
        self._api_client = qc.ApiClient(configuration)
        self._runs = qc.RunsApi(self._api_client)
        self._results = qc.ResultsApi(self._api_client)
        self._milestones = qc.MilestonesApi(self._api_client)
        self._environments = qc.EnvironmentsApi(self._api_client)
        self._plans = qc.PlansApi(self._api_client)

    def close(self) -> None:
        self._api_client.__exit__(None, None, None)

    def __enter__(self) -> "QaseClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # --- runs -----------------------------------------------------------------

    @_api_call("create run")
    def create_run(
        self,
        title: str,
        milestone_id: int | None = None,
        environment_id: int | None = None,
        plan_id: int | None = None,
    ) -> int:
        run = qc.RunCreate(title=title, milestone_id=milestone_id, environment_id=environment_id, plan_id=plan_id)
        return self._runs.create_run(self.project, run).result.id

    @_api_call("complete run")
    def complete_run(self, run_id: int) -> None:
        self._runs.complete_run(self.project, run_id)

    @_api_call("delete run")
    def delete_run(self, run_id: int) -> None:
        self._runs.delete_run(self.project, run_id)

    @_api_call("list runs")
    def list_runs(
        self,
        milestone_id: int | None = None,
        environment_id: int | None = None,
        from_start_time: int | None = None,
        to_start_time: int | None = None,
    ) -> list[qc.Run]:
        return list(
            _paginate(
                lambda limit, offset: self._runs.get_runs(
                    self.project,
                    milestone=milestone_id,
                    environment=environment_id,
                    from_start_time=from_start_time,
                    to_start_time=to_start_time,
                    limit=limit,
                    offset=offset,
                )
            )
        )

    # --- results --------------------------------------------------------------

    @_api_call("submit results")
    def submit_results(self, run_id: int, results: list[qc.ResultCreate]) -> None:
        for start in range(0, len(results), RESULT_BULK_MAX):
            batch = qc.ResultCreateBulk(results=results[start : start + RESULT_BULK_MAX])
            self._results.create_result_bulk(self.project, run_id, batch)

    # --- name -> ID lookup ----------------------------------------------------

    @_api_call("find object by name")
    def find_id(self, kind: QaseObjectKind, name: str) -> int | None:
        """Return the ID of the milestone/environment/plan with exactly this title, or None."""
        list_method = {
            QaseObjectKind.MILESTONE: self._milestones.get_milestones,
            QaseObjectKind.ENVIRONMENT: self._environments.get_environments,
            QaseObjectKind.PLAN: self._plans.get_plans,
        }[kind]
        entities = _paginate(lambda limit, offset: list_method(self.project, limit=limit, offset=offset))
        return next((entity.id for entity in entities if entity.title == name), None)

    def resolve_id(self, kind: QaseObjectKind, value: str | int | None) -> int | None:
        """Resolve a name-or-ID value: digits are used as the ID, anything else is looked up by title."""
        if value is None or value == "":
            return None
        if isinstance(value, int) or str(value).isdigit():
            return int(value)
        object_id = self.find_id(kind, value)
        if object_id is None:
            raise QaseObjectNotFoundError(kind.value, value, self.project)
        LOG.info("Resolved %s %r to ID %s.", kind.value, value, object_id)
        return object_id
