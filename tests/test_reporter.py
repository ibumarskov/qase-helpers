import pytest

from qase_helper.client import QaseClient, QaseObjectKind
from qase_helper.errors import ConfigError, QaseObjectNotFoundError, TestNameTooLongError, UnresolvedCasesError
from qase_helper.junit import TestResult, TestStatus
from qase_helper.reporter import Reporter, ReportOptions

LONG = "x" * 300


def _result(name, status=TestStatus.PASSED):
    return TestResult(name=name, status=status)


@pytest.fixture
def client(mocker):
    fake = mocker.create_autospec(QaseClient, instance=True)
    fake.create_run.return_value = 100
    fake.resolve_id.side_effect = lambda kind, value: None if value is None else 7
    fake.list_case_ids_by_title.return_value = {"t1": [11], "t2": [12], "dup": [21, 22]}
    return fake


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
    client.create_run.assert_called_once_with(
        "Nightly", description=None, milestone_id=7, environment_id=7, plan_id=None
    )
    run_id, payload = client.submit_results.call_args.args
    assert run_id == 100
    assert [(r.case_id, r.case) for r in payload] == [(11, None), (42, None)]
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


def test_exclude_skipped_drops_skipped_results_and_their_long_names(client):
    results = [_result("t1"), _result("t2", TestStatus.SKIPPED), _result(LONG, TestStatus.SKIPPED)]
    summary = Reporter(client).report(results, options=ReportOptions(exclude_skipped=True))
    payload = client.submit_results.call_args.args[1]
    assert [r.case_id for r in payload] == [11]
    assert (summary.results_count, summary.excluded_count) == (1, 2)


def test_skipped_results_are_reported_by_default(client):
    results = [_result("t1"), _result("t2", TestStatus.SKIPPED)]
    summary = Reporter(client).report(results)
    payload = client.submit_results.call_args.args[1]
    assert [r.status for r in payload] == ["passed", "skipped"]
    assert summary.excluded_count == 0


def test_unresolved_cases_fail_before_creating_run(client):
    results = [_result("t1"), _result("new"), _result("dup")]
    with pytest.raises(UnresolvedCasesError) as excinfo:
        Reporter(client).report(results)
    assert excinfo.value.missing == ["new"]
    assert excinfo.value.ambiguous == {"dup": [21, 22]}
    client.create_run.assert_not_called()
    client.submit_results.assert_not_called()


def test_case_map_overrides_title_lookup(client):
    Reporter(client).report([_result("dup"), _result("t1")], {"dup": 99})
    assert [r.case_id for r in client.submit_results.call_args.args[1]] == [99, 11]


def test_fully_mapped_report_skips_case_lookup(client):
    Reporter(client).report([_result("anything")], {"anything": 5})
    client.list_case_ids_by_title.assert_not_called()


def test_prepare_is_read_only(client):
    plan = Reporter(client).prepare([_result("t1"), _result(LONG)], {LONG: 42}, ReportOptions(milestone="M"))
    assert plan.case_ids == {"t1": 11, LONG: 42}
    assert plan.milestone_id == 7
    client.create_run.assert_not_called()
    client.submit_results.assert_not_called()


def test_run_description_is_passed_to_new_run(client):
    Reporter(client).report([_result("t1")], options=ReportOptions(run_title="R", run_description="Build 42"))
    assert client.create_run.call_args.kwargs["description"] == "Build 42"


def test_too_long_run_description_fails_before_any_api_call(client):
    with pytest.raises(ConfigError, match="at most 10000"):
        Reporter(client).report([_result("t1")], options=ReportOptions(run_description="x" * 10001))
    assert client.mock_calls == []
