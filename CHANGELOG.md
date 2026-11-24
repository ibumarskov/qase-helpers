# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0]

First release.

### Added
- `qase-helper report`: submit JUnit XML results to a new or existing Qase test run.
  Milestone, environment and plan accept a name or an ID (names are resolved through the Qase API).
- `report` submits every result against a case ID: taken from the case-ID map, or found by the exact case title
  in the project. Tests without exactly one matching case fail the command before a run is created, so results
  are never submitted by title (which Qase either rejects or turns into duplicate cases).
  `report --dry-run` resolves case IDs with read-only API calls.
- Test names longer than `max_length` (default 255) must be listed in the case-ID map file. Otherwise `report`
  fails with an error before calling the Qase API.
- `report --exclude-skipped`: do not report skipped tests to the run.
- `report --run-description`: description of the created run (also `report.run_description` in the config file).
- `report` prints a link to the test run after uploading results (`qase.app_url` sets the web UI address for
  self-hosted or enterprise Qase).
- `qase-helper cases create`: create automated Qase test cases for tests in a JUnit report that have no case yet
  (not in the case-ID map and no case with the same title in the project), optionally in a given `--suite`.
  The same long-name rule as in `report` applies.
- `qase-helper runs delete`: delete test runs filtered by start date, milestone, environment and title.
  It lists runs only, unless `--yes` is given.
- Layered configuration: CLI options > `QASE_HELPER_*` environment variables > YAML config file > defaults.
- Exception hierarchy rooted at `QaseHelperError`; documented exit codes.
- Example config files: `qase-helper.example.yaml`, `case-ids.example.yaml`.
