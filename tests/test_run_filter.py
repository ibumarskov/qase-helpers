from datetime import date

import pytest

from qase_helper.errors import ConfigError
from qase_helper.run_filter import RunFilter, parse_date


class _Run:
    def __init__(self, title):
        self.title = title


def _titles(runs):
    return [r.title for r in runs]


def test_no_title_filter_keeps_all_runs():
    runs = [_Run("a"), _Run(None)]
    assert RunFilter(since=date(2025, 1, 1)).apply(runs) == runs


def test_title_contains_uses_and_semantics():
    runs = [_Run("nightly regression x"), _Run("nightly regression y"), _Run("smoke x")]
    assert _titles(RunFilter(title_contains=["regression", "x"]).apply(runs)) == ["nightly regression x"]


def test_title_matching_case_sensitivity():
    runs = [_Run("Nightly Regression")]
    assert RunFilter(title_contains=["regression"]).apply(runs) == runs
    assert RunFilter(title_contains=["regression"], case_sensitive=True).apply(runs) == []
    assert RunFilter(title_contains=["Regression"], case_sensitive=True).apply(runs) == runs


def test_none_title_does_not_match_keyword():
    assert RunFilter(title_contains=["x"]).apply([_Run(None)]) == []


def test_date_bounds_are_inclusive_utc_days():
    run_filter = RunFilter(since=date(2025, 1, 1), until=date(2025, 1, 1))
    assert run_filter.from_start_time == 1735689600  # 2025-01-01T00:00:00Z
    assert run_filter.to_start_time == 1735689600 + 86399  # 2025-01-01T23:59:59Z
    assert RunFilter().from_start_time is None
    assert RunFilter().to_start_time is None


def test_since_after_until_is_rejected():
    with pytest.raises(ConfigError, match="must not be later"):
        RunFilter(since=date(2025, 2, 1), until=date(2025, 1, 1))


def test_is_empty():
    assert RunFilter().is_empty
    assert RunFilter(case_sensitive=True).is_empty
    assert not RunFilter(milestone_id=1).is_empty
    assert not RunFilter(title_contains=["x"]).is_empty


def test_parse_date():
    assert parse_date("2025-03-04") == date(2025, 3, 4)
    assert parse_date(None) is None
    with pytest.raises(ConfigError, match="YYYY-MM-DD"):
        parse_date("04.03.2025")
