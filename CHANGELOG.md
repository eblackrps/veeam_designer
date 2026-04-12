# Changelog

All notable changes to Chrome Policy Merge are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/), and this project follows
[Semantic Versioning](https://semver.org/).

## [4.0.1] - 2026-04-12

### Added

- A polished FastAPI web console for mounted workspace operations and browser upload previews
- A dedicated `chrome-policy-merge-web` entry point
- Docker deployment files for self-hosted web use
- Upload bundle export with `merged-policy.json` and synthetic snapshot metadata
- Web/API tests covering preview, bundle download, workspace merge, restore, and path safety

### Changed

- The project is once again presented as a UI-first product, with CLI and API support alongside
  the web experience
- Package metadata and dependencies now include the runtime needed for the web console
- Documentation now treats the web UI and Docker workflow as primary operating paths

### Fixed

- Restored the missing web UI and Docker deployment path after the 4.0.0 modernization release
- Added source-compatible `ui.main:app` support for Uvicorn-based deployments

## [4.0.0] - 2026-04-12

### Added

- A production-ready `chrome_policy_merge` Python package with a typed library API
- A professional `argparse` CLI with `merge` and `restore` commands
- Safe timestamped backup snapshots with `manifest.json` metadata
- Deterministic natural sorting, atomic output writing, structured logging, and dry-run support
- A full pytest suite covering unit and integration behavior
- Ruff, mypy, pre-commit, wheel and sdist builds, and GitHub Actions CI
- Example policy files and expected output for documentation and smoke testing
- Security guidance and migration documentation

### Changed

- Repository structure is now focused on one product: Chrome enterprise policy merging
- JSON input discovery is non-recursive and restricted to intended policy files
- Merge semantics are explicit and documented for replacements, deep dict merges, and list unions
- Backup handling no longer risks silent overwrites of previous snapshots
- Restore now accepts only snapshot directory names from the configured backup root

### Breaking Changes

- The legacy ad hoc `key=value` invocation style has been replaced with a structured `argparse` CLI
- The installable package name is now `chrome-policy-merge`
- The import path is now `chrome_policy_merge`
- The default workflow writes to `merged-policy.json` and archives source files in `backup/`
- Restore is handled through an explicit `restore` command instead of manual file movement
