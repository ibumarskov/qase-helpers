"""Parse JUnit XML reports into SDK-independent :class:`TestResult` objects."""

import html
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from qase_helper.errors import InputFileError


class TestStatus(str, Enum):
    """Result status, using Qase's status slugs as values."""

    __test__ = False  # not a pytest test class

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class TestResult:
    """A single JUnit testcase result."""

    __test__ = False  # not a pytest test class

    name: str
    status: TestStatus
    duration: float = 0.0
    stacktrace: str | None = None


def _element_text(element: ET.Element) -> str:
    """Combine the ``message`` attribute and the element's text, decoding XML/HTML entities."""
    parts = []
    message = element.get("message")
    if message:
        parts.append(html.unescape(message))
    text = "".join(element.itertext()).strip()
    if text:
        parts.append(html.unescape(text))
    return "\n".join(parts)


def _status_of(testcase: ET.Element) -> TestStatus:
    if testcase.find("failure") is not None or testcase.find("error") is not None:
        return TestStatus.FAILED
    if testcase.find("skipped") is not None:
        return TestStatus.SKIPPED
    return TestStatus.PASSED


def _stacktrace_of(testcase: ET.Element) -> str | None:
    parts = [_element_text(child) for child in testcase if child.tag in ("failure", "error")]
    return "\n".join(parts) if parts else None


def _duration_of(testcase: ET.Element) -> float:
    raw = testcase.get("time") or "0"
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return 0.0


def parse_junit(path: str | Path) -> list[TestResult]:
    """Parse every ``<testcase>`` in a JUnit report. Testcases without a name are skipped."""
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
    except FileNotFoundError as exc:
        raise InputFileError(f"JUnit report not found: {path}") from exc
    except OSError as exc:
        raise InputFileError(f"Cannot read JUnit report {path}: {exc}") from exc
    except ET.ParseError as exc:
        raise InputFileError(f"Invalid JUnit XML in {path}: {exc}") from exc

    results = []
    for testcase in root.iter("testcase"):
        name = (testcase.get("name") or "").strip()
        if not name:
            continue
        results.append(
            TestResult(
                name=name,
                status=_status_of(testcase),
                duration=_duration_of(testcase),
                stacktrace=_stacktrace_of(testcase),
            )
        )
    return results


def select_results(results: list[TestResult], exclude_skipped: bool) -> list[TestResult]:
    """Return all results, or all except skipped ones."""
    if not exclude_skipped:
        return list(results)
    return [result for result in results if result.status is not TestStatus.SKIPPED]
