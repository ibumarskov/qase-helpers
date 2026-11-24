from pathlib import Path

import pytest

from qase_helper.case_map import load_case_map, resolve_case_ids, validate_names
from qase_helper.errors import InputFileError, TestNameTooLongError, UnresolvedCasesError


def _write(tmp_path, content):
    path = tmp_path / "case-ids.yaml"
    path.write_text(content)
    return path


def test_loads_mapping_and_strips_titles(tmp_path):
    path = _write(tmp_path, "cases:\n  - title: '  A.test  '\n    case_id: 1\n  - title: B.test\n    case_id: 2\n")
    assert load_case_map(path) == {"A.test": 1, "B.test": 2}


@pytest.mark.parametrize("content", ["", "cases: []\n", "cases:\n"])
def test_empty_file_or_list(tmp_path, content):
    assert load_case_map(_write(tmp_path, content)) == {}


@pytest.mark.parametrize(
    "content, message",
    [
        ("cases:\n  - title: A\n", "must have both"),
        ("cases:\n  - case_id: 1\n", "must have both"),
        ("cases:\n  - just-a-string\n", "must have both"),
        ("cases:\n  - title: A\n    case_id: abc\n", "positive integer"),
        ("cases:\n  - title: A\n    case_id: 0\n", "positive integer"),
        ("cases:\n  - title: A\n    case_id: 1\n  - title: A\n    case_id: 2\n", "duplicate title"),
        ("cases: {a: 1}\n", "'cases' list"),
        ("- a\n", "'cases' list"),
        ("cases: [\n", "Invalid YAML"),
    ],
)
def test_invalid_files(tmp_path, content, message):
    with pytest.raises(InputFileError, match=message):
        load_case_map(_write(tmp_path, content))


def test_missing_file(tmp_path):
    with pytest.raises(InputFileError, match="not found"):
        load_case_map(tmp_path / "missing.yaml")


def test_example_file_is_valid():
    example = Path(__file__).resolve().parent.parent / "case-ids.example.yaml"
    assert len(load_case_map(example)) == 2


LONG = "x" * 300


def test_validate_names_lists_all_unmapped_long_names_once():
    with pytest.raises(TestNameTooLongError) as excinfo:
        validate_names([LONG, "short", LONG + "y", LONG], {}, max_length=255)
    assert excinfo.value.names == [LONG, LONG + "y"]
    assert excinfo.value.max_length == 255


def test_validate_names_accepts_mapped_long_names_and_boundary():
    validate_names([LONG, "z" * 255], {LONG: 1}, max_length=255)


def test_resolve_case_ids_from_map_and_titles():
    ids = resolve_case_ids(["a", "b", "a"], {"b": 7}, {"a": [1], "b": [2, 3]})
    assert ids == {"a": 1, "b": 7}


def test_resolve_case_ids_reports_missing_and_ambiguous():
    with pytest.raises(UnresolvedCasesError) as excinfo:
        resolve_case_ids(["ok", "new", "dup", "new"], {}, {"ok": [1], "dup": [3, 2]})
    assert excinfo.value.missing == ["new"]
    assert excinfo.value.ambiguous == {"dup": [2, 3]}
    message = str(excinfo.value)
    assert "2 test(s) cannot be matched" in message
    assert "cases create" in message
    assert "dup (cases 2, 3)" in message
