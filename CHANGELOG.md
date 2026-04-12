# Changelog

All notable changes to Veeam Designer are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [4.0.2] - 2026-04-12

### Added

- Published refreshed screenshots of the actual Veeam Designer calculator UI under
  `docs/screenshots/`
- Added a corrective `4.0.2` release path so the restored web application can ship cleanly after
  the mistaken tool-only release line

### Changed

- Restored Veeam Designer as a web-first sizing calculator with dedicated VM, NAS, Physical, and
  Replication modes
- Replaced the UI-to-CLI subprocess hop with direct engine calls through `veeam_designer.service`
- Normalized REST and CLI JSON outputs with a versioned `kind` field
- Updated Docker packaging to install the restored application directly from the repository
- Refreshed GitHub Actions to run Ruff, pytest, and package builds
- Reworked release-facing documentation so the repository consistently describes the restored UI,
  CLI, API, screenshots, and Docker workflow

### Fixed

- Fixed API and UI version reporting so the application consistently reports `4.0.2`
- Fixed profile selection so each run starts from the base configuration instead of leaking prior
  profile overrides between requests
- Fixed the physical workload story by giving the web UI a real physical / agent calculator path

## [3.1.0] - 2026-03-01

### Fixed

- Corrected four critical engine math issues in replication sizing, replica storage estimation, WAN
  accelerator transfer conversion, and proxy task thresholds
- Corrected high-severity issues in compliance validation, type hints, network window handling, and
  object-storage immutability overhead
- Added request size limits to the web UI and `/api/design`

## [3.0.0] - 2026-03-01

### Added

- Workload tabs for VM, NAS, Physical, and Replication
- Replication sizing, CDP support, WAN accelerator sizing, licensing, tape, Veeam ONE, and
  compliance modeling
- Downloadable HTML reports and a REST API
- Expanded pytest coverage across the engine and web API

## [2.0.0] - 2026-03-01

### Added

- NAS / unstructured workload sizing
- Backup server sizing enhancements, immutability modeling, and ObjectFirst Orca sizing
- Capacity tier and direct-to-object planning
- Physical / agent support and richer risk scoring
- Docker distribution and automated image publishing

## [1.0.0] - 2026-03-01

### Added

- Initial multi-site Veeam sizing engine
- FastAPI web UI with YAML mode
- CLI project-file support and JSON output
