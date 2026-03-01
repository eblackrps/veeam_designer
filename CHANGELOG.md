# Changelog

All notable changes to veeam-designer are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [3.0.0] – 2026-03-01

### Added
- **Round 1**: Form UX overhaul — HTML datalists for common values, pre-populated defaults, workload type tabs (VM / NAS / Physical / Replication)
- **Round 2**: Replication sizing section — replica storage, CDP proxy + journal sizing, dashboard card
- **Round 3**: NAS / unstructured backup sizing — file proxy sizing, cache repo, dashboard card
- **Round 4**: WAN accelerator sizing (`wan_accel.py`) — source/target appliance count, cache, effective throughput, BCJ window validation
- **Round 5**: Veeam VUL license estimator (`licensing.py`) — workload count, tier (community/standard/enterprise), annual cost
- **Round 6**: LTO tape library sizing (`tape.py`) — cartridge count, scratch pool, slots, drives, media cost
- **Round 7**: Veeam ONE + Enterprise Manager sizing (`veeam_one.py`) — tiered by workload count, DB sizing, EM/VSPC
- **Round 8**: Compliance gap analysis (`compliance.py`) — HIPAA, SOC 2, GDPR, PCI DSS, DORA frameworks
- **Round 9**: Downloadable self-contained HTML design report (`/export/report`)
- **Round 10**: REST API (`/api/health`, `/api/profiles`, `/api/design`), 12-module pytest suite, v3.0.0 packaging

---

## [2.0.0] – 2026-03-01

### Added
- **NAS/Unstructured workload sizing** (`veeam_designer/nas.py`)
  - Cache repo sizing (file-change metadata)
  - File proxy cores and RAM (10 MB/s per core)
  - Compression presets: Media (10%) / Mix (30%) / Docs (50%)
  - GFS retention for NAS workloads
  - Storage-native CFT toggle
- **Backup server sizing overhaul** (`roles.py`)
  - Workload count + concurrent job concurrency formula
  - v13 appliance mode (20% core reduction)
  - Indexing RAM overhead per 50 workloads
  - `ram_gb` and `notes` fields on `BackupServerSizing`
- **ReFS/XFS, immutability, block generation period** (`repo_perf.py`, `sizing.py`)
  - `block_generation_days` replaces hardcoded 7-day synthetic full window
  - Immutability adds 5% repo overhead for XFS metadata
  - Filesystem compatibility notes in blueprint output
- **ObjectFirst Orca node sizing** (`veeam_designer/orca.py`)
  - 96 TB usable per node, 64 concurrent streams
  - Scale-out recommendation at ≥ 3 nodes
  - Wired into `design_veeam_environment()` for `repo_type = object`
- **Capacity tier full modeling + direct-to-object** (`sobr.py`, `cost.py`)
  - `capacity_tier_fraction` controls object offload percentage
  - `direct_to_object` bypasses performance tier entirely
  - Fixed long-standing bug where capacity tier cost was always $0
- **Per-transport proxy sizing + proxy RAM** (`roles.py`)
  - DirectSAN: 20 MB/s/core, 8 GB RAM/proxy
  - HotAdd: 15 MB/s/core, 8 GB RAM/proxy
  - NBD: 5 MB/s/core, 4 GB RAM/proxy
  - Hypervisor-transport compatibility validation notes
  - `transport_mode`, `ram_gb_per_proxy`, `total_proxy_ram_gb` on `ProxySizing`
- **VM Replication + CDP sizing** (`veeam_designer/replication.py`)
  - Bandwidth requirement per RPO window
  - CDP journal storage (rolling window)
  - Dedicated CDP proxy core sizing
  - `--workload-type replication` CLI path
- **Agent/Physical backup support** (`veeam_designer/agent.py`)
  - Network-based throughput model (5 MB/s/core)
  - Agent coordinator sizing per 100 machines
  - Windows VSS / Linux CBT notes
  - `--workload-type physical` CLI path
- **3-year TCO + multi-cloud cost model** (`cost.py`, `config.json`)
  - Cloud providers: AWS S3, Azure Blob, Wasabi, ObjectFirst
  - `cloud_comparison`, `three_year_tco`, `break_even_years` on `CostEstimate`
  - Break-even calculation (cloud vs on-prem over 10-year horizon)
- **Expanded risk scoring** (`risk.py`)
  - Growth forecast risk (> 20% → red)
  - Immutability compliance risk (object storage without immutability → yellow)
  - RPO bandwidth margin risk (weighted excess demand)
- **CLI enhancements** (`cli.py`)
  - `--workload-type vm|nas|physical|replication`
  - All new v2 flags: `--immutability`, `--capacity-tier`, `--refs-xfs`, `--block-generation-days`, etc.
- **Web UI dashboard improvements** (`ui/main.py`, `ui/templates/index.html`)
  - Transport mode + proxy RAM displayed per site
  - Backup server cores + RAM in proxy load panel
  - ObjectFirst Orca card (when `repo_type: object`)
  - 3-year TCO panel with cloud comparison mini-table
  - Per-site risk breakdown now includes growth + immutability + RPO margin factors
  - Simple Form mode: v2 advanced options per site (ReFS/XFS, immutability, capacity tier, direct-to-object, block gen period, concurrent jobs)
- **Docker distribution**
  - `Dockerfile` — Python 3.12-slim, uvicorn entrypoint
  - `docker-compose.yml` — single-service compose file with volume mounts
  - `.dockerignore` — excludes venv, cache, git history
  - `.github/workflows/docker.yml` — build + push to `emb079/veeam-designer` (Docker Hub) and `ghcr.io/eblackrps/veeam-designer` (GHCR) on tag push

### Changed
- `pyproject.toml` version bumped to `2.0.0`
- `config.json` extended with cloud provider cost rates
- `profiles.json` unchanged (backwards compatible)
- `parser.py` extended to dispatch `workload_type: nas|physical|replication` from YAML

---

## [1.0.0] – 2026-03-01

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

Initial preview release (pre-repo, internal distribution).
