"""Exception hierarchy for qase-helper.

Library code raises these instead of exiting; the CLI maps any
:class:`QaseHelperError` to a log message and a non-zero exit code.
"""


class QaseHelperError(Exception):
    """Base class for all expected qase-helper errors."""


class ConfigError(QaseHelperError):
    """Invalid or incomplete configuration (missing token/project, bad config file, bad option value)."""


class InputFileError(QaseHelperError):
    """An input file (JUnit report, case-ID map) is missing or malformed."""


class TestNameTooLongError(QaseHelperError):
    """Test names exceed Qase's limit and have no case-ID mapping."""

    __test__ = False  # not a pytest test class

    def __init__(self, names: list[str], max_length: int):
        self.names = list(names)
        self.max_length = max_length
        listing = "\n".join(f"  - {name}" for name in self.names)
        super().__init__(
            f"{len(self.names)} test name(s) exceed {max_length} characters and have no entry in the "
            f"case-ID map. Add them to the case-ID map file (case_id_map_file / --case-id-map):\n{listing}"
        )


class UnresolvedCasesError(QaseHelperError):
    """JUnit tests that cannot be matched to exactly one Qase test case."""

    def __init__(self, missing: list[str], ambiguous: dict[str, list[int]]):
        self.missing = list(missing)
        self.ambiguous = dict(ambiguous)
        lines = [f"{len(self.missing) + len(self.ambiguous)} test(s) cannot be matched to a Qase test case."]
        if self.missing:
            lines.append(
                f"No case with this title ({len(self.missing)}); create them with `qase-helper cases create` "
                "or add them to the case-ID map:"
            )
            lines += [f"  - {name}" for name in self.missing]
        if self.ambiguous:
            lines.append(f"Several cases with this title ({len(self.ambiguous)}); add them to the case-ID map:")
            lines += [f"  - {name} (cases {', '.join(map(str, ids))})" for name, ids in self.ambiguous.items()]
        super().__init__("\n".join(lines))


class QaseObjectNotFoundError(QaseHelperError):
    """A Qase object (milestone, environment, plan) could not be found by name."""

    def __init__(self, kind: str, name: str, project: str):
        self.kind = kind
        self.name = name
        self.project = project
        super().__init__(f'{kind.capitalize()} "{name}" not found in Qase project {project}.')


class QaseApiError(QaseHelperError):
    """A call to the Qase API failed."""

    def __init__(self, operation: str, status: int | None = None, reason: str | None = None, body: str | None = None):
        self.operation = operation
        self.status = status
        self.reason = reason
        self.body = body
        details = " ".join(str(part) for part in (status, reason) if part)
        message = f"Qase API request failed: {operation}"
        if details:
            message += f" ({details})"
        if body:
            message += f": {body}"
        super().__init__(message)
