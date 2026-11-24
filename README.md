# qase-helper

A CLI for reporting JUnit XML test results to the [Qase](https://qase.io) test
management platform, creating Qase test cases from JUnit reports and cleaning up
old Qase test runs. Built on the Qase
API v1 ([`qase-api-client`](https://github.com/qase-tms/qase-python/tree/main/qase-api-client)).

Commands:

- `qase-helper report`: submit the results of a JUnit report to a new or existing Qase test run.
- `qase-helper cases create`: create Qase test cases for the tests in a JUnit report that have no case yet.
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
| Web UI URL (for the run link) | — | `QASE_HELPER_APP_URL` | `qase.app_url` | `https://app.qase.io` if `api_host` is not set |
| Run title | `report --run-title` | `QASE_HELPER_RUN_TITLE` | `report.run_title` | `Automated run` |
| Run description | `report --run-description` | `QASE_HELPER_RUN_DESCRIPTION` | `report.run_description` | none |
| Existing run ID | `report --run-id` | `QASE_HELPER_RUN_ID` | `report.run_id` | none (create a run) |
| Milestone | `report --milestone` | `QASE_HELPER_MILESTONE` | `report.milestone` | none |
| Environment | `report --environment` | `QASE_HELPER_ENVIRONMENT` | `report.environment` | none |
| Test plan | `report --plan` | `QASE_HELPER_PLAN` | `report.plan` | none |
| Complete created run | `report --complete/--no-complete` | `QASE_HELPER_COMPLETE_RUN` | `report.complete_run` | `true` |
| Case-ID map file | `report`/`cases create --case-id-map` | `QASE_HELPER_CASE_ID_MAP` | `junit.case_id_map_file` | none |
| Max test name length (1-255) | `report`/`cases create --max-length` | `QASE_HELPER_MAX_LENGTH` | `junit.max_length` | `255` |
| Ignore skipped tests | `report`/`cases create --exclude-skipped/--include-skipped` | `QASE_HELPER_EXCLUDE_SKIPPED` | `junit.exclude_skipped` | `false` |
| Suite for new cases | `cases create --suite` | `QASE_HELPER_SUITE` | `cases.suite` | none (project root) |
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
    --run-description "Build 1234, commit abc123" \
    --milestone "Release 2.5" --environment staging

# Report into an existing run (an existing run is never completed by this command)
qase-helper -p DEMO report results.xml --run-id 123

# Do not report skipped tests
qase-helper -p DEMO report results.xml --exclude-skipped

# Validate the report and resolve case IDs without creating a run (read-only API calls)
qase-helper -p DEMO report results.xml --case-id-map case-ids.yaml --dry-run
```

`--milestone`, `--environment` and `--plan` accept either a numeric ID or a
title. Titles are resolved to IDs through the Qase API, and an unknown title is
an error. These options, as well as `--run-title` and `--run-description`, apply
only when a new run is created.

After a successful upload, `report` prints a summary and a link to the run, for example
`Run URL: https://app.qase.io/run/DEMO/dashboard/123`. With a custom `api_host`
(self-hosted or enterprise Qase), set `app_url` to the address of your Qase web UI,
otherwise no link is printed.

Each JUnit `<testcase>` becomes one result: `<failure>` or `<error>` maps to
`failed` (the message and text go into the stacktrace), `<skipped>` maps to
`skipped`, and anything else maps to `passed`.

Every result is submitted against a case ID. Before a run is created, `report`
matches each test to exactly one Qase case:

1. If the test name is in the case-ID map, the case ID from the map is used.
2. Otherwise the test name must equal the title of exactly one case in the project.

If any test has no matching case, or its title is shared by several cases, `report`
fails before creating a run and lists those tests. Create the missing cases with
`qase-helper cases create`, and add tests with ambiguous titles to the case-ID map.
`report` never submits results by title: depending on the project settings, Qase
either rejects such results or creates a duplicate case for each of them.

With `--exclude-skipped`, skipped tests are left out of the run entirely. They are
also exempt from the long-name check described below.

#### Long test names and the case-ID map

Qase limits case titles to 255 characters. Neither `report` nor `cases create`
truncates names. If a test name is longer than `max_length`, it must be listed in
the case-ID map, and its result is then reported against that case ID. Otherwise
the command fails **before calling the Qase API** and lists every offending test
name. Cases for such tests have to be created in Qase manually and added to the map.

The case-ID map is a YAML file keyed by the full JUnit testcase name (see
[`case-ids.example.yaml`](case-ids.example.yaml)):

```yaml
cases:
  - title: "TestSuite.test_some_very_long_descriptive_name_..."
    case_id: 1234
```

Any test can be listed here, not only long ones, to pin it to a specific case.

### Create test cases

```shell
# Show which cases would be created (reads the project, creates nothing)
qase-helper -p DEMO cases create results.xml --suite "Regression" --dry-run

# Create them
qase-helper -p DEMO cases create results.xml --suite "Regression" --case-id-map case-ids.yaml
```

For every unique test name in the report, the command creates a case unless:

- the name is listed in the case-ID map, or
- a case with exactly this title already exists anywhere in the project.

New cases are titled with the test name and marked as automated. `--suite` takes
a suite name or ID; the suite must already exist. Without `--suite` the cases are
created at the project root. The same long-name rule as in `report` applies, and
`--exclude-skipped` ignores skipped tests. The created cases are printed as
`[case_id] name`.

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
| `1` | Error: invalid configuration, invalid input file, test name too long without a mapping, test without exactly one matching Qase case, Qase object not found, Qase API failure, or some runs failed to delete |
| `2` | Invalid command-line usage |

Errors are written to stderr. Command output, such as the report summary and the list of runs, goes to stdout.

## Development

The development tools (pytest, ruff) are in the `dev` extra. Pass `--extra dev`
to every `uv run`: without it, `uv run` syncs the environment without the extra
and removes them (or set `UV_EXTRA=dev` once in the shell).

```shell
uv run --extra dev pytest
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .   # or `ruff format .` to reformat
```

Code layout (`src/qase_helper/`):

| Module | Responsibility |
|---|---|
| `cli/` | Typer commands (`main.py` global options, `report.py`, `cases.py`, `runs.py`) |
| `config.py` | Layered settings: CLI > env > YAML > defaults |
| `errors.py` | Exception hierarchy (`QaseHelperError` and subclasses) |
| `junit.py` | JUnit XML parsing into `TestResult`, skipped-test filtering |
| `case_map.py` | Case-ID map loading; the long test name check |
| `client.py` | The only module that talks to the Qase API v1 SDK |
| `reporter.py` | The `report` workflow: ID resolution, run lifecycle, result submission |
| `cases.py` | The `cases create` workflow: decide which cases are missing and create them |
| `run_filter.py` | Run selection criteria for `runs delete` |
