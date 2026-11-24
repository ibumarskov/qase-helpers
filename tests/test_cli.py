import pytest
from typer.testing import CliRunner

from qase_helper import __version__
from qase_helper.cli.main import app
from qase_helper.errors import QaseApiError

runner = CliRunner()
LONG = "x" * 300


def _invoke(*args):
    return runner.invoke(app, list(args))


@pytest.fixture
def junit(write_junit):
    return write_junit(f'<testcase name="t1"/><testcase name="{LONG}"><failure message="boom"/></testcase>')


@pytest.fixture
def case_map(tmp_path):
    path = tmp_path / "case-ids.yaml"
    path.write_text(f"cases:\n  - title: '{LONG}'\n    case_id: 42\n")
    return path


@pytest.fixture
def client_cls(mocker):
    cls = mocker.patch("qase_helper.cli.report.QaseClient")
    mocker.patch("qase_helper.cli.runs.QaseClient", cls)
    mocker.patch("qase_helper.cli.cases.QaseClient", cls)
    client = cls.return_value.__enter__.return_value
    client.project = "PRJ"
    client.create_run.return_value = 100
    client.resolve_id.side_effect = lambda kind, value: None if value is None else 7
    client.list_case_ids_by_title.return_value = {"t1": [11], "t2": [12]}
    return cls


def test_version():
    result = _invoke("--version")
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_only_supported_commands():
    result = _invoke("--help")
    assert result.exit_code == 0
    for command in ("report", "runs", "cases"):
        assert command in result.output
    for removed in ("analyze", "convert", "truncate", "delete-runs"):
        assert removed not in result.output


def test_report_dry_run_rejects_long_name_without_mapping(junit, client_cls):
    result = _invoke("--token", "t", "-p", "PRJ", "report", str(junit), "--dry-run")
    assert result.exit_code == 1
    assert "exceed 255 characters" in result.output
    client_cls.return_value.__enter__.return_value.list_case_ids_by_title.assert_not_called()


def test_report_dry_run_resolves_case_ids_without_writing(junit, case_map, client_cls):
    result = _invoke("--token", "t", "-p", "PRJ", "report", str(junit), "--case-id-map", str(case_map), "--dry-run")
    assert result.exit_code == 0, result.output
    assert "2 result(s) would be reported" in result.output
    assert "case_id=11" in result.output and "(title)" in result.output
    assert "case_id=42" in result.output and "(map" in result.output
    client = client_cls.return_value.__enter__.return_value
    client.create_run.assert_not_called()
    client.submit_results.assert_not_called()


def test_report_dry_run_requires_credentials(junit, case_map):
    result = _invoke("report", str(junit), "--case-id-map", str(case_map), "--dry-run")
    assert result.exit_code == 1
    assert "token is required" in result.output


def test_report_unknown_test_fails_before_creating_run(write_junit, client_cls):
    junit = write_junit('<testcase name="t1"/><testcase name="brand new test"/>')
    result = _invoke("--token", "t", "-p", "PRJ", "report", str(junit))
    assert result.exit_code == 1
    assert "1 test(s) cannot be matched to a Qase test case" in result.output
    assert "brand new test" in result.output
    client = client_cls.return_value.__enter__.return_value
    client.create_run.assert_not_called()
    client.submit_results.assert_not_called()


def test_report_requires_credentials(junit, case_map):
    result = _invoke("report", str(junit), "--case-id-map", str(case_map))
    assert result.exit_code == 1
    assert "token is required" in result.output


def test_report_submits(junit, case_map, client_cls):
    result = _invoke(
        "--token", "tok", "-p", "PRJ", "report", str(junit), "--case-id-map", str(case_map), "--milestone", "M1"
    )
    assert result.exit_code == 0, result.output
    client_cls.assert_called_once_with("tok", "PRJ", None)
    client = client_cls.return_value.__enter__.return_value
    client.complete_run.assert_called_once_with(100)
    assert "Reported 2 result(s) to run 100" in result.output
    assert "Run URL: https://app.qase.io/run/PRJ/dashboard/100" in result.output


@pytest.mark.parametrize("source", ["cli", "env"])
def test_report_run_description(monkeypatch, junit, case_map, client_cls, source):
    args = ["--token", "t", "-p", "PRJ", "report", str(junit), "--case-id-map", str(case_map)]
    if source == "cli":
        args += ["--run-description", "Build 42"]
    else:
        monkeypatch.setenv("QASE_HELPER_RUN_DESCRIPTION", "Build 42")
    result = _invoke(*args)
    assert result.exit_code == 0, result.output
    create_run = client_cls.return_value.__enter__.return_value.create_run
    assert create_run.call_args.kwargs["description"] == "Build 42"


def test_report_settings_from_config_and_env(tmp_path, monkeypatch, junit, case_map, client_cls):
    config = tmp_path / "qase-helper.yaml"
    config.write_text(
        f"qase:\n  project: CFG\njunit:\n  case_id_map_file: '{case_map}'\nreport:\n  complete_run: false\n"
    )
    monkeypatch.setenv("QASE_HELPER_TOKEN", "envtok")
    result = _invoke("report", str(junit))
    assert result.exit_code == 0, result.output
    client_cls.assert_called_once_with("envtok", "CFG", None)
    client_cls.return_value.__enter__.return_value.complete_run.assert_not_called()


def test_report_missing_junit_file():
    result = _invoke("report", "missing.xml", "--dry-run")
    assert result.exit_code == 1
    assert "JUnit report not found" in result.output


def test_bad_config_file_is_reported():
    result = _invoke("--config", "missing.yaml", "report", "x.xml", "--dry-run")
    assert result.exit_code == 1
    assert "Config file not found" in result.output


def _run(id_, title):
    return type("Run", (), {"id": id_, "title": title, "status_text": "passed", "start_time": None})()


def test_runs_delete_requires_a_filter(client_cls):
    result = _invoke("--token", "t", "-p", "PRJ", "runs", "delete", "--yes")
    assert result.exit_code == 1
    assert "At least one filter is required" in result.output
    client_cls.return_value.__enter__.return_value.delete_run.assert_not_called()


def test_runs_delete_without_yes_only_lists(client_cls):
    client = client_cls.return_value.__enter__.return_value
    client.list_runs.return_value = [_run(1, "nightly a"), _run(2, "smoke")]
    result = _invoke("--token", "t", "-p", "PRJ", "runs", "delete", "--title-contains", "nightly")
    assert result.exit_code == 0, result.output
    assert "1 run(s) match" in result.output
    assert "Pass --yes" in result.output
    client.delete_run.assert_not_called()


def test_runs_delete_dry_run_never_deletes(client_cls):
    client = client_cls.return_value.__enter__.return_value
    client.list_runs.return_value = [_run(1, "nightly")]
    result = _invoke("--token", "t", "-p", "PRJ", "runs", "delete", "--until", "2025-01-01", "--dry-run", "--yes")
    assert result.exit_code == 0, result.output
    client.delete_run.assert_not_called()


def test_runs_delete_with_yes(client_cls):
    client = client_cls.return_value.__enter__.return_value
    client.list_runs.return_value = [_run(1, "a"), _run(2, "b")]
    result = _invoke("--token", "t", "-p", "PRJ", "runs", "delete", "--since", "2025-01-01", "--milestone", "M1", "-y")
    assert result.exit_code == 0, result.output
    assert client.list_runs.call_args.kwargs["milestone_id"] == 7
    assert [c.args[0] for c in client.delete_run.call_args_list] == [1, 2]
    assert "Deleted 2 run(s), 0 failed." in result.output


def test_runs_delete_partial_failure_exits_1(client_cls):
    client = client_cls.return_value.__enter__.return_value
    client.list_runs.return_value = [_run(1, "a"), _run(2, "b")]
    client.delete_run.side_effect = [QaseApiError("delete run", 500), None]
    result = _invoke("--token", "t", "-p", "PRJ", "runs", "delete", "--until", "2025-01-01", "--yes")
    assert result.exit_code == 1
    assert "Deleted 1 run(s), 1 failed." in result.output


def test_runs_delete_invalid_date(client_cls):
    result = _invoke("--token", "t", "-p", "PRJ", "runs", "delete", "--since", "01.01.2025")
    assert result.exit_code == 1
    assert "YYYY-MM-DD" in result.output


def test_report_exclude_skipped_dry_run(write_junit, client_cls):
    junit = write_junit(
        f'<testcase name="t1"/><testcase name="t2"><skipped/></testcase><testcase name="{LONG}"><skipped/></testcase>'
    )
    result = _invoke("--token", "t", "-p", "PRJ", "report", str(junit), "--exclude-skipped", "--dry-run")
    assert result.exit_code == 0, result.output
    assert "1 result(s) would be reported" in result.output
    assert "2 skipped excluded" in result.output
    assert "t2" not in result.output


def test_report_exclude_skipped_from_env(monkeypatch, write_junit, client_cls):
    junit = write_junit('<testcase name="t1"/><testcase name="t2"><skipped/></testcase>')
    monkeypatch.setenv("QASE_HELPER_EXCLUDE_SKIPPED", "true")
    result = _invoke("--token", "t", "-p", "PRJ", "report", str(junit))
    assert result.exit_code == 0, result.output
    payload = client_cls.return_value.__enter__.return_value.submit_results.call_args.args[1]
    assert len(payload) == 1
    assert "1 skipped excluded" in result.output


def test_cases_create(junit, case_map, client_cls):
    client = client_cls.return_value.__enter__.return_value
    client.list_case_titles.return_value = set()
    client.create_cases.return_value = [501]
    result = _invoke(
        "--token", "t", "-p", "PRJ", "cases", "create", str(junit), "--case-id-map", str(case_map), "--suite", "Smoke"
    )
    assert result.exit_code == 0, result.output
    client.create_cases.assert_called_once_with(["t1"], suite_id=7)
    assert "Created 1 case(s) in suite 7" in result.output
    assert "[501] t1" in result.output
    assert "1 are in the case-ID map" in result.output


def test_cases_create_dry_run(junit, case_map, client_cls):
    client = client_cls.return_value.__enter__.return_value
    client.list_case_titles.return_value = {"t1"}
    result = _invoke(
        "--token", "t", "-p", "PRJ", "cases", "create", str(junit), "--case-id-map", str(case_map), "--dry-run"
    )
    assert result.exit_code == 0, result.output
    client.create_cases.assert_not_called()
    assert "0 case(s) would be created in the project root" in result.output
    assert "1 test(s) already have a case" in result.output


def test_cases_create_long_name_without_mapping(junit, client_cls):
    result = _invoke("--token", "t", "-p", "PRJ", "cases", "create", str(junit))
    assert result.exit_code == 1
    assert "exceed 255 characters" in result.output
    client_cls.return_value.__enter__.return_value.create_cases.assert_not_called()


def test_cases_create_requires_credentials(junit, case_map):
    result = _invoke("cases", "create", str(junit), "--case-id-map", str(case_map))
    assert result.exit_code == 1
    assert "token is required" in result.output
