import pytest

from qase_helper.client import QaseClient, QaseObjectKind
from qase_helper.errors import QaseObjectNotFoundError, TestNameTooLongError
from qase_helper.junit import TestResult, TestStatus
from qase_helper.reporter import Reporter, ReportOptions, validate_names

LONG = "x" * 300


def _result(name, status=TestStatus.PASSED):
    return TestResult(name=name, status=status)


@pytest.fixture
def client(mocker):
    fake = mocker.create_autospec(QaseClient, instance=True)
    fake.create_run.return_value = 100
    fake.resolve_id.side_effect = lambda kind, value: None if value is None else 7
    return fake


def test_validate_names_lists_all_unmapped_long_names():
    results = [_result(LONG), _result("short"), _result(LONG + "y"), _result(LONG)]
    with pytest.raises(TestNameTooLongError) as excinfo:
        validate_names(results, {}, max_length=255)
    assert excinfo.value.names == [LONG, LONG + "y"]
    assert excinfo.value.max_length == 255


def test_validate_names_accepts_mapped_long_names_and_boundary():
    validate_names([_result(LONG), _result("z" * 255)], {LONG: 1}, max_length=255)


def test_long_name_without_mapping_fails_before_any_api_call(client):
    with pytest.raises(TestNameTooLongError):
        Reporter(client).report([_result("ok"), _result(LONG)])
    assert client.mock_calls == []


def test_creates_resolves_submits_and_completes(client):
    results = [_result("t1"), _result(LONG, TestStatus.FAILED)]
    options = ReportOptions(run_title="Nightly", milestone="Release 2.5", environment="5")

    summary = Reporter(client).report(results, {LONG: 42}, options)

    client.resolve_id.assert_any_call(QaseObjectKind.MILESTONE, "Release 2.5")
    client.resolve_id.assert_any_call(QaseObjectKind.ENVIRONMENT, "5")
    client.create_run.assert_called_once_with("Nightly", milestone_id=7, environment_id=7, plan_id=None)
    run_id, payload = client.submit_results.call_args.args
    assert run_id == 100
    assert payload[0].case.title == "t1"
    assert payload[1].case_id == 42 and payload[1].case is None
    client.complete_run.assert_called_once_with(100)
    assert (summary.run_id, summary.run_created, summary.run_completed, summary.results_count) == (100, True, True, 2)


def test_no_complete(client):
    summary = Reporter(client).report([_result("t1")], options=ReportOptions(complete_run=False))
    client.complete_run.assert_not_called()
    assert not summary.run_completed


def test_existing_run_is_not_created_or_completed(client):
    summary = Reporter(client).report([_result("t1")], options=ReportOptions(run_id=55, milestone="ignored"))
    client.create_run.assert_not_called()
    client.resolve_id.assert_not_called()
    client.complete_run.assert_not_called()
    assert client.submit_results.call_args.args[0] == 55
    assert (summary.run_id, summary.run_created, summary.run_completed) == (55, False, False)


def test_unknown_milestone_aborts_before_creating_run(client):
    client.resolve_id.side_effect = QaseObjectNotFoundError("milestone", "nope", "PRJ")
    with pytest.raises(QaseObjectNotFoundError):
        Reporter(client).report([_result("t1")], options=ReportOptions(milestone="nope"))
    client.create_run.assert_not_called()
    client.submit_results.assert_not_called()
