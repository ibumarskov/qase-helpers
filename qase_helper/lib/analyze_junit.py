"""
Parse JUnit XML and check failed/errored tests against known issues.

Returns the list of unmatched failures (failures that have no matching
known issue by title + error substring).

Failure/error element text may contain XML entities (e.g. &#xA; for newline,
&lt; &gt; for angle brackets). We decode them so the full trace can be
compared with multiline YAML.
"""

import html
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from qase_helper.lib.known_issues import load_known_issues, matches_known_issue


@dataclass
class FailedTest:
    """A failed or errored test case: name and full error text."""
    name: str
    error_text: str


def _decode_failure_text(raw: str) -> str:
    """
    Decode XML/HTML entities in failure text so the trace is comparable
    with multiline YAML (e.g. &#xA; -> newline, &lt; -> <, &gt; -> >).
    """
    if not raw:
        return raw
    return html.unescape(raw)


def _collect_error_text(element: ET.Element) -> str:
    """
    Concatenate message attribute and element text (including nested).
    Decode XML entities in the body so special characters and newlines
    match the original trace.
    """
    parts = []
    msg = element.get("message")
    if msg:
        parts.append(_decode_failure_text(msg))
    text = "".join(element.itertext())
    if text:
        text = _decode_failure_text(text.strip())
        parts.append(text)
    return "\n".join(parts)


def _get_failed_tests(root: ET.Element) -> list[FailedTest]:
    """
    Iterate over testcase elements; for each with at least one failure or
    error, collect name and concatenated error text from all failure/error
    children.
    """
    result = []
    for testcase in root.iter("testcase"):
        name = testcase.get("name") or ""
        error_parts = []
        for child in testcase:
            if child.tag in ("failure", "error"):
                error_parts.append(_collect_error_text(child))
        if not error_parts:
            continue
        result.append(
            FailedTest(name=name, error_text="\n".join(error_parts))
        )
    return result


def analyze(junit_path: str | Path, yaml_path: str | Path) -> list[FailedTest]:
    """
    Load JUnit report and known-issues YAML, match failures by title + error
    containment. Return the list of failed tests that have no matching
    known issue (unmatched failures).
    """
    tree = ET.parse(junit_path)
    root = tree.getroot()
    failed = _get_failed_tests(root)
    issues = load_known_issues(yaml_path)
    unmatched = []
    for ft in failed:
        if any(
            matches_known_issue(ft.name, ft.error_text, issue)
            for issue in issues
        ):
            continue
        unmatched.append(ft)
    return unmatched
