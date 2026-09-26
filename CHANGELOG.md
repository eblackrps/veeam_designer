# Changelog

All notable changes to Veeam Designer are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [5.0.0a5] - 2026-09-25

### Fixed

- Replaced the browser report button's hidden-iframe print path with a user-gesture report window
  that works reliably across desktop and mobile browsers and includes an explicit Print / Save PDF
  action
- Removed shared process-global export state; CSV and server-rendered report endpoints are now
  stateless and operate only on the project YAML supplied with each request
- Exposed the VM forecast horizon so annual growth no longer relies on an invisible engine default
- Unified generic object-repository and Direct-to-Object behavior across repository capacity,
  performance, SOBR, and cost planning
- Prevented unsupported reverse-incremental and independently scheduled synthetic-full chain modes
  from being modeled as valid direct-object designs
- Corrected capacity-tier offload so only retained/GFS backup data is tier-eligible; local
  transformation headroom is no longer incorrectly offloaded
- Removed stale fixed-capacity Object First auto-sizing and the fabricated immutability overhead
  percentage; Object First helper sizing now requires an explicit current node capacity
- Removed hardcoded provider-price comparisons and calculated cloud break-even output that looked
  more precise than the configured planning inputs support
- Removed stale unused GFS/pricing configuration knobs and aligned fallback configuration with the
  packaged runtime configuration

### Changed

- Added explicit Capacity Tier Offload and Capacity Tier Object Lock controls to the VM builder
- Normalized JSON, CSV, and report export behavior around the current result bundle
- Reports now identify cost figures as configured planning rates instead of live provider pricing
- Added regression coverage for browser report behavior, stateless exports, object-target chain
  validation, capacity-tier math, Object First explicit sizing, all workload browser bundles, and
  removal of fake pricing precision

## [5.0.0a4] - 2026-09-25

### Fixed

- Rebuilt VM repository capacity around VBR 13 N+1 retention, backup-chain behavior, compound
  growth, separate operational headroom, and explicit immutability duration instead of blanket
  weekly-full math or arbitrary immutability percentages
- Separated CDP short-term retention from CDP RPO, corrected steady-state replication bandwidth,
  and aligned WAN accelerator Auto, Low, High, and Direct modes with explicit reduction assumptions
- Replaced fabricated precision in NAS, Agent, tape, Veeam ONE, and licensing with isolated formulas,
  known-answer tests, and explicit assumptions where Veeam does not define a universal value
- Removed inherited repository compression/deduplication from the automatic WAN sizing path

### Changed

- Added UI inputs for immutability duration, WAN accelerator mode, NAS source concurrency, Agent
  proxy concurrency, and CDP retention/measured write I/O without redesigning the interface
- Updated reports and summaries to separate retained data from operational headroom and to label
  configured cost values as planning assumptions
- Updated sizing documentation to describe the hardened formulas, source ambiguities, and remaining
  engineering assumptions

## [5.0.0a3] - 2026-09-25

### Changed

- Cleaned the repository documentation and package metadata around the current v5 workflow
- Removed obsolete 4.x screenshots and their package/ignore references
- Refreshed the checked-in example project and added a smoke test to keep it executable
- Aligned contributor validation steps with the browser JavaScript CI gate
- Corrected the package maturity classifier to Alpha while the 5.0 prerelease line is active
- Replaced the ambiguous `VD` hero mark with a neutral stacked-infrastructure icon
- Shortened the hero heading and supporting copy to direct product language
- Removed browser-engine readiness/status copy from the visible interface
- Reduced large-heading weight and scale on narrow screens

## [5.0.0a2] - 2026-09-25

### Changed

- Rebuilt the shared server/Pages interface around a flatter, professional architecture-workbench
  visual system with clearer hierarchy, tighter spacing, and fewer competing panels
- Added platform-aware and workload-aware progressive disclosure so VMware-only, Hyper-V, AHV, and
  Proxmox controls appear only when relevant
- Reorganized VM site inputs into capacity/protection and data-path/repository sections
- Made the architecture-results panel sticky on desktop and simplified export controls
- Replaced terminal-style blueprint and cost blocks with readable decision summaries while keeping
  raw JSON in the advanced results section
- Reduced the visual weight of YAML/API editing and advanced sizing controls without removing them
- Improved responsive behavior for tablet and mobile layouts
- Removed stale 4.x UI screenshots from the README so the repository landing page does not
  misrepresent the 5.x interface

### Added

- Added visible unit suffixes for capacity, percentage, time, bandwidth, and throughput inputs
- Added explicit browser-state visibility synchronization for workload and platform changes

## [5.0.0a1] - 2026-09-25

### Added

- Added native Proxmox VE and Nutanix AHV worker sizing with explicit host, cluster, concurrency,
  per-worker task, compute, memory, and disk outputs
- Added Hyper-V proxy sizing that combines Veeam's vSphere-method throughput calculation with
  Hyper-V-specific CPU, RAM, disk, and concurrent-task minimums
- Added Veeam Software Appliance deployment sizing and exposed deployment mode in the browser and CLI
- Added current Windows/Linux backup-server concurrency memory minimums and both Software Appliance
  minimum disks to architecture output
- Added Veeam Infrastructure Appliance deployment sizing for VMware proxies, separating proxy-role
  throughput resources from appliance allocation and disk overhead
- Added platform-worker details to API payloads, dashboards, browser reports, and human summaries
- Added Proxmox VE to the web calculator and CLI/interactive workflows

### Changed

- Stopped applying VMware proxy assumptions to Proxmox VE and Nutanix AHV workers; Hyper-V now
  follows Veeam's documented direction to use the vSphere proxy sizing method with Hyper-V-specific
  system minimums
- Preserved the existing proxy payload as a compatibility adapter while introducing a dedicated
  `platform_workers` role model
- Updated platform recommendations to distinguish VMware/Hyper-V proxies from AHV/Proxmox workers
- Bumped browser local-storage keys for the v5 form schema

### Fixed

- Corrected AHV guidance that previously described AHV data movers as VMware-style proxy VMs

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
