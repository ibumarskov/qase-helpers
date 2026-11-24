import pytest

from qase_helper.cases import CaseCreateOptions, CaseCreator, plan_cases
from qase_helper.client import QaseClient, QaseObjectKind
from qase_helper.errors import QaseObjectNotFoundError, TestNameTooLongError
from qase_helper.junit import TestResult, TestStatus

LONG = "x" * 300


def _result(name, status=TestStatus.PASSED):
    return TestResult(name=name, status=status)


@pytest.fixture
def client(mocker):
    fake = mocker.create_autospec(QaseClient, instance=True)
    fake.resolve_id.side_effect = lambda kind, value: None if value is None else 5
    fake.list_case_titles.return_value = {"exists"}
    fake.create_cases.side_effect = lambda titles, suite_id=None: list(range(100, 100 + len(titles)))
    return fake


def test_plan_cases_splits_unique_names_in_order():
    plan = plan_cases(["new1", "exists", "mapped", "new2", "new1"], {"mapped": 1}, {"exists"})
    assert plan.to_create == ["new1", "new2"]
    assert plan.existing == ["exists"]
    assert plan.mapped == ["mapped"]


def test_case_map_wins_over_existing_title():
    plan = plan_cases(["t"], {"t": 1}, {"t"})
    assert (plan.to_create, plan.existing, plan.mapped) == ([], [], ["t"])


def test_creates_only_missing_cases(client):
    results = [_result("new1"), _result("exists"), _result(LONG), _result("new1", TestStatus.FAILED)]
    summary = CaseCreator(client).create(results, {LONG: 42}, CaseCreateOptions(suite="Smoke"))

    client.resolve_id.assert_called_once_with(QaseObjectKind.SUITE, "Smoke")
    client.create_cases.assert_called_once_with(["new1"], suite_id=5)
    assert summary.created == {"new1": 100}
    assert summary.suite_id == 5
    assert summary.plan.existing == ["exists"]
    assert summary.plan.mapped == [LONG]


def test_no_suite_means_project_root(client):
    summary = CaseCreator(client).create([_result("new1")])
    client.create_cases.assert_called_once_with(["new1"], suite_id=None)
    assert summary.suite_id is None


def test_long_name_without_mapping_fails_before_any_api_call(client):
    with pytest.raises(TestNameTooLongError) as excinfo:
        CaseCreator(client).create([_result("ok"), _result(LONG)])
    assert excinfo.value.names == [LONG]
    assert client.mock_calls == []


def test_exclude_skipped(client):
    results = [_result("new1"), _result("skipped", TestStatus.SKIPPED), _result(LONG, TestStatus.SKIPPED)]
    summary = CaseCreator(client).create(results, options=CaseCreateOptions(exclude_skipped=True))
    client.create_cases.assert_called_once_with(["new1"], suite_id=None)
    assert summary.excluded_count == 2


def test_dry_run_reads_but_does_not_create(client):
    summary = CaseCreator(client).create([_result("new1"), _result("exists")], options=CaseCreateOptions(dry_run=True))
    client.list_case_titles.assert_called_once()
    client.create_cases.assert_not_called()
    assert summary.plan.to_create == ["new1"]
    assert summary.created == {}


def test_nothing_to_create_skips_api_write(client):
    summary = CaseCreator(client).create([_result("exists")])
    client.create_cases.assert_not_called()
    assert summary.created == {}


def test_unknown_suite_aborts(client):
    client.resolve_id.side_effect = QaseObjectNotFoundError("suite", "nope", "PRJ")
    with pytest.raises(QaseObjectNotFoundError):
        CaseCreator(client).create([_result("new1")], options=CaseCreateOptions(suite="nope"))
    client.create_cases.assert_not_called()
