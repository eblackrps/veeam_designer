# Veeam Designer

[![CI](https://github.com/eblackrps/veeam_designer/actions/workflows/ci.yml/badge.svg)](https://github.com/eblackrps/veeam_designer/actions/workflows/ci.yml)
[![Pages](https://github.com/eblackrps/veeam_designer/actions/workflows/pages.yml/badge.svg)](https://github.com/eblackrps/veeam_designer/actions/workflows/pages.yml)

Veeam Designer is a web-first sizing and architecture calculator for Veeam backup environments.
It turns workload, retention, platform, and recovery requirements into infrastructure sizing,
capacity, WAN, risk, and cost guidance.

**Live calculator:** https://eblackrps.github.io/veeam_designer/

Current development line: **5.0.0a9**

## What It Sizes

- **VM Backup** — multi-site repository, data-mover, backup-server, retention, WAN, and cost planning
- **VMware vSphere** — transport-aware proxy sizing with managed OS or Veeam Infrastructure Appliance deployment
- **Microsoft Hyper-V** — throughput-aware proxy sizing with Hyper-V CPU, RAM, disk, and task minimums
- **Nutanix AHV** — native Veeam worker sizing
- **Proxmox VE** — native Veeam worker sizing with Hot-Add/NBD placement guidance
- **NAS** — file proxy, cache, repository, retention, and growth planning
- **Physical** — agent/general-purpose proxy, repository, and network sizing
- **Replication / CDP** — replica capacity, average changed-data WAN, CDP retention, and proxy sizing

The same Python sizing engine is used by the browser edition, FastAPI service, CLI, and Docker image.

## Quick Start

### GitHub Pages

Use the browser-hosted calculator without installing anything:

https://eblackrps.github.io/veeam_designer/

The Pages edition runs the packaged Python engine in-browser with Pyodide and supports the guided
builder, YAML workflow, JSON/CSV export, and printable reports.

### Local Web App

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install .
veeam-designer-web --host 127.0.0.1 --port 8000
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Open `http://127.0.0.1:8000/run`.

### Docker

```bash
docker run --rm -p 8000:8000 emb079/veeam-designer:latest
```

Or build the repository locally:

```bash
docker compose up --build
```

Open `http://localhost:8000/run`.

## Web UI

The shared web interface is streamlined for day-to-day sizing work:

- platform-specific controls appear only when they apply
- advanced parameters stay out of the primary workflow
- YAML remains available for automation and hand editing
- raw JSON stays under the advanced results section
- the same frontend is used by FastAPI, Docker, and GitHub Pages

A completed calculation produces summary metrics, per-site sizing, warnings, configured
planning-cost output, structured JSON, CSV, and a printable report.

## CLI

Run a project file:

```bash
veeam-designer --project-file example-project.yml
```

Return JSON:

```bash
veeam-designer --project-file example-project.yml --json
```

Show available options:

```bash
veeam-designer --help
veeam-designer-web --help
```

## REST API

The FastAPI deployment exposes:

- `GET /api/health`
- `GET /api/profiles`
- `POST /api/design`
- `POST /export/csv`
- `POST /export/report` for VM or multi-site YAML

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/design \
  -H "Content-Type: text/plain" \
  --data-binary @example-project.yml
```

## Project Files

The included [example-project.yml](example-project.yml) is the reference multi-site project.

A minimal VM project looks like:

```yaml
profile: enterprise
workload_type: vm
total_data_tb: 50
daily_change_percent: 5
backup_window_hours: 8
vm_count: 100
hypervisor: vmware
repo_type: sobr
deployment_mode: software_appliance
proxy_deployment_mode: managed_os
```

## Sizing Guidance

Veeam Designer distinguishes published vendor guidance from planning assumptions. Current platform
models include VMware proxies, Hyper-V proxies, AHV workers, Proxmox workers, backup-server
deployment requirements, hardened repository compute, WAN acceleration, NAS, replication/CDP,
Veeam ONE, tape, licensing consumption, and configured cost planning.

Repository outputs separate retained backup data from operational headroom. Commercial licensing
pricing is not inferred. Storage cost output uses explicit local/object planning rates, and Capacity
Tier cost modeling distinguishes Copy, Move, and Copy + Move. Move/Copy + Move local-capacity
reduction is derived from the configured operational restore window and modeled inactive-chain
age instead of an arbitrary offload percentage.

See [docs/assumptions.md](docs/assumptions.md) for formulas, caveats, and source links.

## Development

Install the development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the same validation gates used by CI:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy .
node --check ui/static/app.js
python -m pytest -q
python -m build
python tools/build_pages.py --output _site
```

## Repository Layout

```text
veeam_designer/   sizing engine and shared services
ui/               FastAPI app, templates, and browser assets
tests/            regression and smoke tests
tools/            build helpers
docs/             assumptions and deployment documentation
config.json       calculator tuning parameters
profiles.json     sizing profiles
example-project.yml
```

## Documentation

- [Sizing assumptions and sources](docs/assumptions.md)
- [Deployment](docs/deployment.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Security](SECURITY.md)

## License

Released under the [MIT License](LICENSE).
