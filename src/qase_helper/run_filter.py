"""Selection criteria for Qase test runs (used by ``runs delete``)."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone

from qase_helper.errors import ConfigError


def parse_date(value: str | None) -> date | None:
    """Parse a YYYY-MM-DD string."""
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ConfigError(f"Invalid date {value!r}: expected YYYY-MM-DD.") from exc


@dataclass(frozen=True)
class RunFilter:
    """Runs matching ALL given criteria are selected.

    ``since``/``until`` are inclusive UTC dates applied to the run start time.
    ``title_contains`` substrings must all appear in the run title.
    """

    since: date | None = None
    until: date | None = None
    milestone_id: int | None = None
    environment_id: int | None = None
    title_contains: list[str] = field(default_factory=list)
    case_sensitive: bool = False

    def __post_init__(self):
        if self.since and self.until and self.since > self.until:
            raise ConfigError(f"--since ({self.since}) must not be later than --until ({self.until}).")

    @property
    def is_empty(self) -> bool:
        return not (self.since or self.until or self.milestone_id or self.environment_id or self.title_contains)

    @property
    def from_start_time(self) -> int | None:
        """Start of ``since`` day as a UTC unix timestamp."""
        if self.since is None:
            return None
        return int(datetime.combine(self.since, time.min, tzinfo=timezone.utc).timestamp())

    @property
    def to_start_time(self) -> int | None:
        """End of ``until`` day as a UTC unix timestamp (inclusive)."""
        if self.until is None:
            return None
        return int(datetime.combine(self.until, time.max, tzinfo=timezone.utc).timestamp())

    def matches_title(self, title: str | None) -> bool:
        if not self.title_contains:
            return True
        haystack = title or ""
        needles = self.title_contains
        if not self.case_sensitive:
            haystack = haystack.lower()
            needles = [needle.lower() for needle in needles]
        return all(needle in haystack for needle in needles)

    def apply(self, runs: list) -> list:
        """Client-side filtering for criteria the API does not support (title substrings)."""
        return [run for run in runs if self.matches_title(run.title)]
