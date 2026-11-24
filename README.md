# qase-helper

A CLI for reporting JUnit XML test results to the [Qase](https://qase.io) test
management platform and for cleaning up old Qase test runs. Built on the Qase
API v1 ([`qase-api-client`](https://github.com/qase-tms/qase-python/tree/main/qase-api-client)).

Commands:

- `qase-helper report`: submit the results of a JUnit report to a new or existing Qase test run.
- `qase-helper runs delete`: delete test runs that match a filter (date range, milestone, environment, title).

## Installation

Requires Python 3.10+.

```shell
# From a checkout, with uv (https://docs.astral.sh/uv/)
uv sync
uv run qase-helper --help

# Or install into any environment
pip install .
qase-helper --version
```

## Configuration

Every setting can be supplied in three ways. When a setting is given in more than one place, this is the precedence:

1. CLI option, for example `--project DEMO`.
2. Environment variable, for example `QASE_HELPER_PROJECT=DEMO`.
3. YAML config file. The default is `./qase-helper.yaml`; override it with `--config/-c PATH` or `QASE_HELPER_CONFIG`.

See [`qase-helper.example.yaml`](qase-helper.example.yaml) for an annotated example.
A missing default config file is fine; an explicitly given path that does not
exist is an error, and so are unknown sections or keys in the file.

| Setting | CLI option | Environment variable | YAML key | Default |
|---|---|---|---|---|
| API token | `--token` | `QASE_HELPER_TOKEN` or `QASE_TOKEN` | `qase.token` | none (required) |
| Project code | `-p/--project` | `QASE_HELPER_PROJECT` | `qase.project` | none (required) |
| API URL | `--api-host` | `QASE_HELPER_API_HOST` | `qase.api_host` | Qase SaaS |
| Run title | `report --run-title` | `QASE_HELPER_RUN_TITLE` | `report.run_title` | `Automated run` |
| Existing run ID | `report --run-id` | `QASE_HELPER_RUN_ID` | `report.run_id` | none (create a run) |
| Milestone | `report --milestone` | `QASE_HELPER_MILESTONE` | `report.milestone` | none |
| Environment | `report --environment` | `QASE_HELPER_ENVIRONMENT` | `report.environment` | none |
| Test plan | `report --plan` | `QASE_HELPER_PLAN` | `report.plan` | none |
| Case-ID map file | `report --case-id-map` | `QASE_HELPER_CASE_ID_MAP` | `report.case_id_map_file` | none |
| Max test name length | `report --max-length` | `QASE_HELPER_MAX_LENGTH` | `report.max_length` | `255` |
| Complete created run | `report --complete/--no-complete` | `QASE_HELPER_COMPLETE_RUN` | `report.complete_run` | `true` |
| Exclude skipped tests | `report --exclude-skipped/--include-skipped` | `QASE_HELPER_EXCLUDE_SKIPPED` | `report.exclude_skipped` | `false` |
| Log level | `-v` / `-vv` / `--log-level` | `QASE_HELPER_LOG_LEVEL` | `logging.level` | `WARNING` |
| Log file | `--log-file` | `QASE_HELPER_LOG_FILE` | `logging.file` | none (stderr only) |

Global options (`--config`, `--token`, `--project`, `--api-host`, `-v`,
`--log-level`, `--log-file`) go **before** the command name:
`qase-helper -p DEMO report results.xml`.

Keep the API token in `QASE_HELPER_TOKEN` (for example a CI secret) rather than
in the config file or on the command line.

## Usage

### Report results

```shell
export QASE_HELPER_TOKEN=...

# Create a new run, submit the results and complete the run
qase-helper -p DEMO report results.xml --run-title "Nightly 2025-01-31" \
    --milestone "Release 2.5" --environment staging

# Report into an existing run (an existing run is never completed by this command)
qase-helper -p DEMO report results.xml --run-id 123

# Do not report skipped tests
qase-helper -p DEMO report results.xml --exclude-skipped

# Parse and validate the report without calling the Qase API
qase-helper report results.xml --case-id-map case-ids.yaml --dry-run
```

`--milestone`, `--environment` and `--plan` accept either a numeric ID or a
title. Titles are resolved to IDs through the Qase API, and an unknown title is
an error. These options apply only when a new run is created.

Each JUnit `<testcase>` becomes one result: `<failure>` or `<error>` maps to
`failed` (the message and text go into the stacktrace), `<skipped>` maps to
`skipped`, and anything else maps to `passed`. Results are matched to Qase cases by
the testcase name, and Qase creates cases that do not exist yet.

With `--exclude-skipped`, skipped tests are left out of the run entirely. They are
also exempt from the long-name check described below.

#### Long test names and the case-ID map

Qase limits case titles to 255 characters. `report` never truncates names. If a
test name is longer than `max_length`, it must be listed in the case-ID map, and
its result is then reported against that case ID. Otherwise `report` fails
**before calling the Qase API** and lists every offending test name.

The case-ID map is a YAML file keyed by the full JUnit testcase name (see
[`case-ids.example.yaml`](case-ids.example.yaml)):

```yaml
cases:
  - title: "TestSuite.test_some_very_long_descriptive_name_..."
    case_id: 1234
```

Any test can be listed here, not only long ones, to pin it to a specific case.

### Delete old runs

```shell
# List runs started before 2025-01-01 whose title contains "nightly"
qase-helper -p DEMO runs delete --until 2024-12-31 --title-contains nightly

# ...and delete them
qase-helper -p DEMO runs delete --until 2024-12-31 --title-contains nightly --yes
```

Filters can be combined, and a run is selected only when it matches all of them:

- `--since` and `--until` take a `YYYY-MM-DD` date. Both are inclusive and use the UTC run start time.
- `--milestone` and `--environment` take a name or an ID.
- `--title-contains` is repeatable. Matching is case-insensitive unless `--case-sensitive` is given.

At least one filter is required. Without `--yes` the command only lists the
matching runs, and `--dry-run` never deletes, even together with `--yes`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Error: invalid configuration, invalid input file, test name too long without a mapping, Qase object not found, Qase API failure, or some runs failed to delete |
| `2` | Invalid command-line usage |

Errors are written to stderr. Command output, such as the report summary and the list of runs, goes to stdout.

## Development

```shell
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format .
```

Code layout (`src/qase_helper/`):

| Module | Responsibility |
|---|---|
| `cli/` | Typer commands (`main.py` global options, `report.py`, `runs.py`) |
| `config.py` | Layered settings: CLI > env > YAML > defaults |
| `errors.py` | Exception hierarchy (`QaseHelperError` and subclasses) |
| `junit.py` | JUnit XML parsing into `TestResult` |
| `case_map.py` | Case-ID map loading and validation |
| `client.py` | The only module that talks to the Qase API v1 SDK |
| `reporter.py` | The `report` workflow: name validation, ID resolution, run lifecycle |
| `run_filter.py` | Run selection criteria for `runs delete` |
