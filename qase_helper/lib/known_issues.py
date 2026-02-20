"""
Load and match known-issues from YAML.

Schema:
  tests:
    - title: <QASE_TEST_NAME>   # must match JUnit testcase name
      errors: |
        <expected error log snippet>
      defects: <QASE_DEFECT_ID>

Matching: A failed test matches a known issue iff (1) test name equals the
issue's title, and (2) the issue's errors string (after normalization) is
contained in the test's error output (after normalization). If a known issue
has empty errors, matching is by title only (any failure with that name is
considered known). Duplicate titles in YAML: any match wins.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class KnownIssue:
    """A known issue entry: test title, expected error snippet, defect ID."""
    title: str
    errors: str
    defects: str


def _normalize_text(text: str) -> str:
    """Strip and collapse runs of whitespace/newlines to a single space."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def load_known_issues(path: str | Path) -> list[KnownIssue]:
    """
    Load known issues from a YAML file.

    Expects top-level key 'tests' with a list of dicts, each having
    'title', 'errors' (optional, default ''), and 'defects'.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "tests" not in data:
        return []
    result = []
    for entry in data["tests"]:
        if not isinstance(entry, dict):
            continue
        title = entry.get("title")
        errors = entry.get("errors", "") or ""
        defects = entry.get("defects", "")
        if title is None:
            continue
        result.append(
            KnownIssue(
                title=str(title).strip(),
                errors=str(errors).strip() if errors else "",
                defects=str(defects).strip() if defects else "",
            )
        )
    return result


def matches_known_issue(
    test_name: str,
    error_text: str,
    issue: KnownIssue,
    normalize: bool = True,
) -> bool:
    """
    Return True if this failed test matches the given known issue.

    - Title must match exactly (after stripping).
    - If issue.errors is non-empty, it must be contained in the test's
      error_text (both optionally normalized). If issue.errors is empty,
      matching is by title only.
    """
    if (test_name or "").strip() != (issue.title or "").strip():
        return False
    if not issue.errors:
        return True
    expected = _normalize_text(issue.errors) if normalize else issue.errors
    actual = _normalize_text(error_text) if normalize else error_text
    return expected in actual
