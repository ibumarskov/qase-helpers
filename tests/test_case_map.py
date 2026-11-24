from pathlib import Path

import pytest

from qase_helper.case_map import load_case_map
from qase_helper.errors import InputFileError


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
