"""Create Qase test cases from the tests found in a JUnit report."""

import logging
from dataclasses import dataclass, field

from qase_helper.case_map import validate_names
from qase_helper.client import QaseClient, QaseObjectKind
from qase_helper.config import DEFAULT_MAX_LENGTH
from qase_helper.junit import TestResult, select_results

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaseCreateOptions:
    """``suite`` accepts a name or a numeric ID; ``None`` creates cases at the project root."""

    suite: str | None = None
    max_length: int = DEFAULT_MAX_LENGTH
    exclude_skipped: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class CasePlan:
    """Unique test names split by what happens to them."""

    to_create: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)  # a case with this exact title already exists
    mapped: list[str] = field(default_factory=list)  # listed in the case-ID map


@dataclass(frozen=True)
class CaseCreateSummary:
    plan: CasePlan
    created: dict[str, int]  # name -> new case ID; empty on dry run
    suite_id: int | None
    excluded_count: int = 0


def plan_cases(names: list[str], case_map: dict[str, int], existing_titles: set[str]) -> CasePlan:
    """Decide, for each unique name (in order), whether to create a case for it."""
    plan = CasePlan()
    for name in dict.fromkeys(names):
        if name in case_map:
            plan.mapped.append(name)
        elif name in existing_titles:
            plan.existing.append(name)
        else:
            plan.to_create.append(name)
    return plan


class CaseCreator:
    """Creates a Qase test case for every JUnit test that has no case yet."""

    def __init__(self, client: QaseClient):
        self._client = client

    def create(
        self,
        results: list[TestResult],
        case_map: dict[str, int] | None = None,
        options: CaseCreateOptions | None = None,
    ) -> CaseCreateSummary:
        case_map = case_map or {}
        options = options or CaseCreateOptions()

        selected = select_results(results, options.exclude_skipped)
        names = [result.name for result in selected]
        # Validate before any API call: a too-long name cannot be a case title.
        validate_names(names, case_map, options.max_length)

        suite_id = self._client.resolve_id(QaseObjectKind.SUITE, options.suite)
        plan = plan_cases(names, case_map, self._client.list_case_titles())
        LOG.info(
            "%d test(s) need a case, %d already exist, %d are in the case-ID map.",
            len(plan.to_create),
            len(plan.existing),
            len(plan.mapped),
        )

        created: dict[str, int] = {}
        if plan.to_create and not options.dry_run:
            ids = self._client.create_cases(plan.to_create, suite_id=suite_id)
            created = dict(zip(plan.to_create, ids, strict=False))
            LOG.info("Created %d case(s).", len(created))

        return CaseCreateSummary(
            plan=plan, created=created, suite_id=suite_id, excluded_count=len(results) - len(selected)
        )
