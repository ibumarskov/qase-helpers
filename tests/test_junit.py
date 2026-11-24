import pytest

from qase_helper.errors import InputFileError
from qase_helper.junit import TestStatus, parse_junit


def test_passed_testcase(write_junit):
    [result] = parse_junit(write_junit('<testcase classname="c" name="t1" time="1.5"/>'))
    assert result.name == "t1"
    assert result.status is TestStatus.PASSED
    assert result.duration == 1.5
    assert result.stacktrace is None


def test_failed_testcase_collects_message_and_text(write_junit):
    cases = '<testcase name="t1" time="0.2"><failure message="boom &lt;x&gt;">trace&#xA;line2</failure></testcase>'
    [result] = parse_junit(write_junit(cases))
    assert result.status is TestStatus.FAILED
    assert "boom <x>" in result.stacktrace
    assert "trace\nline2" in result.stacktrace


def test_error_counts_as_failed(write_junit):
    [result] = parse_junit(write_junit('<testcase name="t1"><error message="oops"/></testcase>'))
    assert result.status is TestStatus.FAILED


def test_skipped(write_junit):
    [result] = parse_junit(write_junit('<testcase name="t1"><skipped/></testcase>'))
    assert result.status is TestStatus.SKIPPED


def test_unnamed_testcases_are_ignored_and_bad_time_is_zero(write_junit):
    results = parse_junit(write_junit('<testcase name=""/><testcase name="t2" time="abc"/>'))
    assert [r.name for r in results] == ["t2"]
    assert results[0].duration == 0.0


def test_missing_file(tmp_path):
    with pytest.raises(InputFileError, match="not found"):
        parse_junit(tmp_path / "missing.xml")


def test_invalid_xml(tmp_path):
    path = tmp_path / "bad.xml"
    path.write_text("<testsuite><testcase")
    with pytest.raises(InputFileError, match="Invalid JUnit XML"):
        parse_junit(path)
