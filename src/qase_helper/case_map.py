"""Load the test-name -> Qase case-ID map from YAML.

Schema::

    cases:
      - title: <full JUnit testcase name>
        case_id: <int>

Tests in the map are reported against the given case ID instead of being
matched by title. This is required for test names longer than Qase's limit
(255 characters), whose names cannot be used as a case title, and for tests
whose title is shared by several cases.
"""

from collections.abc import Iterable
from pathlib import Path

import yaml

from qase_helper.errors import InputFileError, TestNameTooLongError, UnresolvedCasesError


def load_case_map(path: str | Path) -> dict[str, int]:
    """Load the mapping. Raises InputFileError on a missing file, bad schema or duplicate titles."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError as exc:
        raise InputFileError(f"Case-ID map file not found: {path}") from exc
    except OSError as exc:
        raise InputFileError(f"Cannot read case-ID map file {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise InputFileError(f"Invalid YAML in case-ID map file {path}: {exc}") from exc

    if not data:
        return {}
    if not isinstance(data, dict) or not isinstance(data.get("cases") or [], list):
        raise InputFileError(f"Case-ID map file {path} must contain a 'cases' list.")

    mapping: dict[str, int] = {}
    for index, entry in enumerate(data.get("cases") or []):
        where = f"{path}: cases[{index}]"
        if not isinstance(entry, dict) or entry.get("title") is None or entry.get("case_id") is None:
            raise InputFileError(f"{where} must have both 'title' and 'case_id'.")
        title = str(entry["title"]).strip()
        case_id = entry["case_id"]
        if isinstance(case_id, bool) or not isinstance(case_id, int) or case_id <= 0:
            raise InputFileError(f"{where}: case_id must be a positive integer, got {case_id!r}.")
        if title in mapping:
            raise InputFileError(f"{where}: duplicate title {title!r}.")
        mapping[title] = case_id
    return mapping


def validate_names(names: Iterable[str], case_map: dict[str, int], max_length: int) -> None:
    """Raise TestNameTooLongError for every name longer than ``max_length`` that is not in ``case_map``."""
    too_long = [name for name in names if len(name) > max_length and name not in case_map]
    if too_long:
        raise TestNameTooLongError(list(dict.fromkeys(too_long)), max_length)


def resolve_case_ids(
    names: Iterable[str], case_map: dict[str, int], ids_by_title: dict[str, list[int]]
) -> dict[str, int]:
    """Map each test name to a Qase case ID: from the case-ID map, else by exact case title.

    Raises UnresolvedCasesError listing every name with no matching case or with several.
    """
    resolved: dict[str, int] = {}
    missing: list[str] = []
    ambiguous: dict[str, list[int]] = {}
    for name in dict.fromkeys(names):
        if name in case_map:
            resolved[name] = case_map[name]
            continue
        ids = ids_by_title.get(name, [])
        if len(ids) == 1:
            resolved[name] = ids[0]
        elif ids:
            ambiguous[name] = sorted(ids)
        else:
            missing.append(name)
    if missing or ambiguous:
        raise UnresolvedCasesError(missing, ambiguous)
    return resolved
