"""Load the test-name -> Qase case-ID map from YAML.

Schema::

    cases:
      - title: <full JUnit testcase name>
        case_id: <int>

Tests in the map are reported against the given case ID instead of being
matched by title. This is required for test names longer than Qase's limit
(255 characters): their names cannot be sent as a case title.
"""

from pathlib import Path

import yaml

from qase_helper.errors import InputFileError


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
