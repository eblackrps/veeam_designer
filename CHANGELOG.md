# Changelog

All notable changes to Veeam Designer are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [4.0.4] - 2026-04-12

### Added

- Added [docs/assumptions.md](docs/assumptions.md) to document which formulas are calibrated to
  published Veeam guidance and which outputs remain planning heuristics
- Added regression coverage for backup server workload bands, hardened repository host sizing,
  WAN accelerator digest sizing, and NAS incremental-forever behavior
- Added refreshed README screenshots so the published docs show the calibrated `4.0.4` UI state

### Changed

- Calibrated VMware proxy sizing around Veeam transport guidance, a conservative NBD heuristic,
  and explicit effective-capacity reporting in payloads, dashboards, and reports
- Reworked automatic WAN accelerator sizing to use projected VM source size, carry daily change
  rate into the accelerator model, and surface digest/free-space requirements in reports
- Aligned NAS sizing with Veeam unstructured-data guidance by ignoring NAS GFS counts, removing a
  synthetic disk-cache placeholder for disk targets, and using the configured repository warning
  threshold consistently
- Updated deployment docs so `main` pushes refresh GitHub Pages and the `latest` Docker image,
  while `v4.0.4` publishes the matching versioned container tag

### Fixed

- Fixed dashboard and report proxy-capacity calculations so they no longer rely on stale
  hardcoded transport values
- Fixed hypervisor naming drift between the UI and the role-sizing engine for Hyper-V and AHV
- Fixed profile defaults so legacy proxy-throughput profile values no longer silently change the
  transport-aware calculator

## [4.0.3] - 2026-04-12

### Added

- Added a GitHub Pages build pipeline that publishes a browser-hosted calculator using the same
  packaged sizing engine
- Added packaged fallback configuration resources so wheel installs and the Pages edition carry the
  same defaults and sizing profiles as the repo checkout
- Added regression tests for packaged config fallbacks, browser bundles, and the Pages build output

### Changed

- Rewrote the hero copy to present the calculator more clearly and professionally
- Reworked the main web shell so the local FastAPI app and the Pages edition share the same front
  end structure and result rendering
- Updated the README and deployment docs to document the GitHub Pages workflow alongside Docker and
  local installs

### Fixed

- Fixed dropdown styling so dark-theme select controls and option menus remain readable before and
  after selection
- Fixed manual YAML mode so saved hand-edited project files are not overwritten on page load

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
