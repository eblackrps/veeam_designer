# Changelog

All notable changes to veeam-designer are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [1.0.0] – 2025-12-15

First stable release.

### Added
- Multi-site sizing engine (`veeam_designer/`)
  - Repository footprint calculation with GFS and growth projection
  - Proxy count and core sizing per site
  - SOBR layout design with performance and capacity tiers
  - WAN / RPO feasibility analysis
  - Risk scoring engine
  - Cost modeling: on-premises vs. object storage
- FastAPI web UI (`ui/`)
  - Simple form mode for guided site entry
  - YAML mode for direct project file editing
  - Blueprint and Cost output rendered in browser
- CLI entry point (`veeam-designer`)
  - `--project-file` flag for file-based input
  - `--json` flag for machine-readable output
  - Interactive mode for guided input
- Profile presets: MSP, SMB, Enterprise, Custom (`profiles.json`)
- Tunable engine parameters via `config.json`
- Support for backup types: synthetic full, forever-forward incremental, reverse incremental
- Repo types: SOBR, direct, object storage
- Transport modes: DirectSAN, on-host HotAdd

### Fixed
- `config.json` cleaned to valid JSON (removed non-standard inline comments)

---

## [0.95] – 2025-12-15

Initial preview release.
