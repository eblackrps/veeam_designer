# Changelog

All notable changes to Chrome Policy Merge are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/), and this project
follows [Semantic Versioning](https://semver.org/).

## [4.0.0] - 2026-04-12

### Added

- A production-ready `chrome_policy_merge` Python package with a typed library API.
- A professional `argparse` CLI with `merge` and `restore` commands.
- Safe timestamped backup snapshots with `manifest.json` metadata.
- Deterministic natural sorting, atomic output writing, structured logging, and dry-run support.
- A full pytest suite covering unit and integration behavior.
- Ruff, mypy, pre-commit, wheel and sdist builds, and GitHub Actions CI.
- Example policy files and expected output for documentation and smoke testing.
- Security guidance and migration documentation.

### Changed

- Repository structure is now focused on one product: Chrome enterprise policy merging.
- JSON input discovery is non-recursive and restricted to intended policy files.
- Merge semantics are explicit and documented for replacements, deep dict merges, and list unions.
- Backup handling no longer risks silent overwrites of previous snapshots.
- Restore now accepts only snapshot directory names from the configured backup root.

### Breaking Changes

- The legacy ad hoc `key=value` invocation style has been replaced with a structured `argparse` CLI.
- The installable package name is now `chrome-policy-merge`.
- The import path is now `chrome_policy_merge`.
- The default workflow now writes to `merged-policy.json` and archives source files in `backup/`.
- Restore is handled through an explicit `restore` command instead of manual file movement.

### Migration Notes

- Replace legacy direct-script execution with `chrome-policy-merge merge <input_directory>`.
- Replace legacy merge-key handling with one `--merge-key` flag per top-level policy key.
- If you relied on implicit overwrites, review `--strict` and the documented merge semantics before automating upgrades.
