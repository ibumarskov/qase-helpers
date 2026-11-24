import pytest
import qase.api_client_v1 as qc
from qase.api_client_v1.exceptions import ApiException

from qase_helper.client import PAGE_SIZE, RESULT_BULK_MAX, QaseClient, QaseObjectKind, to_result_create
from qase_helper.errors import QaseApiError, QaseObjectNotFoundError
from qase_helper.junit import TestResult, TestStatus


@pytest.fixture
def apis(mocker):
    names = ["RunsApi", "ResultsApi", "MilestonesApi", "EnvironmentsApi", "PlansApi"]
    return {name: mocker.patch(f"qase_helper.client.qc.{name}").return_value for name in names}


@pytest.fixture
def client(apis):
    return QaseClient(token="tok", project="PRJ")


def _list_response(entities):
    response = type("Response", (), {})()
    response.result = type("Result", (), {"entities": entities})()
    return response


def _entity(id_, title):
    return type("Entity", (), {"id": id_, "title": title})()


def test_create_run(apis, client):
    apis["RunsApi"].create_run.return_value = qc.IdResponse(status=True, result=qc.IdResponseAllOfResult(id=123))
    assert client.create_run("My Run", milestone_id=5, environment_id=6, plan_id=7) == 123
    project, run_create = apis["RunsApi"].create_run.call_args.args
    assert project == "PRJ"
    assert (run_create.title, run_create.milestone_id, run_create.environment_id, run_create.plan_id) == (
        "My Run",
        5,
        6,
        7,
    )


def test_submit_results_is_batched(apis, client):
    results = [qc.ResultCreate(status="passed") for _ in range(RESULT_BULK_MAX + 10)]
    client.submit_results(1, results)
    calls = apis["ResultsApi"].create_result_bulk.call_args_list
    assert [len(call.args[2].results) for call in calls] == [RESULT_BULK_MAX, 10]
    assert calls[0].args[:2] == ("PRJ", 1)


def test_complete_and_delete_run(apis, client):
    client.complete_run(42)
    client.delete_run(43)
    apis["RunsApi"].complete_run.assert_called_once_with("PRJ", 42)
    apis["RunsApi"].delete_run.assert_called_once_with("PRJ", 43)


def test_list_runs_paginates(apis, client):
    full = [_entity(i, f"run {i}") for i in range(PAGE_SIZE)]
    apis["RunsApi"].get_runs.side_effect = [_list_response(full), _list_response([_entity(999, "last")])]
    runs = client.list_runs(milestone_id=1, from_start_time=10)
    assert len(runs) == PAGE_SIZE + 1
    second_call = apis["RunsApi"].get_runs.call_args_list[1]
    assert second_call.kwargs["offset"] == PAGE_SIZE
    assert second_call.kwargs["milestone"] == 1
    assert second_call.kwargs["from_start_time"] == 10


def test_api_exception_is_wrapped(apis, client):
    apis["RunsApi"].delete_run.side_effect = ApiException(status=403, reason="Forbidden")
    with pytest.raises(QaseApiError, match="delete run.*403 Forbidden") as excinfo:
        client.delete_run(1)
    assert excinfo.value.status == 403


@pytest.mark.parametrize(
    "kind, api, method",
    [
        (QaseObjectKind.MILESTONE, "MilestonesApi", "get_milestones"),
        (QaseObjectKind.ENVIRONMENT, "EnvironmentsApi", "get_environments"),
        (QaseObjectKind.PLAN, "PlansApi", "get_plans"),
    ],
)
def test_resolve_id_by_name(apis, client, kind, api, method):
    getattr(apis[api], method).return_value = _list_response([_entity(1, "other"), _entity(7, "Release 2.5")])
    assert client.resolve_id(kind, "Release 2.5") == 7


def test_resolve_id_numeric_and_empty_values_skip_api(apis, client):
    assert client.resolve_id(QaseObjectKind.MILESTONE, "42") == 42
    assert client.resolve_id(QaseObjectKind.MILESTONE, 43) == 43
    assert client.resolve_id(QaseObjectKind.MILESTONE, None) is None
    apis["MilestonesApi"].get_milestones.assert_not_called()


def test_resolve_id_not_found(apis, client):
    apis["PlansApi"].get_plans.return_value = _list_response([_entity(1, "other")])
    with pytest.raises(QaseObjectNotFoundError, match='Plan "missing" not found in Qase project PRJ'):
        client.resolve_id(QaseObjectKind.PLAN, "missing")


def test_to_result_create_by_title_and_by_case_id():
    result = TestResult(name="t1", status=TestStatus.FAILED, duration=1.25, stacktrace="boom")
    by_title = to_result_create(result)
    assert by_title.case.title == "t1"
    assert by_title.case_id is None
    assert (by_title.status, by_title.time_ms, by_title.stacktrace) == ("failed", 1250, "boom")

    by_id = to_result_create(result, case_id=9)
    assert by_id.case_id == 9
    assert by_id.case is None
