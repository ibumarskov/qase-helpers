# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0]

First release.

### Added
- `qase-helper report`: submit JUnit XML results to a new or existing Qase test run.
  Milestone, environment and plan accept a name or an ID (names are resolved through the Qase API).
- Test names longer than `max_length` (default 255) must be listed in the case-ID map file. Otherwise `report`
  fails with an error before calling the Qase API.
- `report --exclude-skipped`: do not report skipped tests to the run.
- `qase-helper runs delete`: delete test runs filtered by start date, milestone, environment and title.
  It lists runs only, unless `--yes` is given.
- Layered configuration: CLI options > `QASE_HELPER_*` environment variables > YAML config file > defaults.
- Exception hierarchy rooted at `QaseHelperError`; documented exit codes.
- Example config files: `qase-helper.example.yaml`, `case-ids.example.yaml`.
