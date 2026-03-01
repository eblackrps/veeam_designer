# Veeam Designer

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Release](https://img.shields.io/github/v/release/eblackrps/veeam_designer)
![Docker Pulls](https://img.shields.io/docker/pulls/emb079/veeam-designer)

A multi-site Veeam backup environment sizing and architecture tool built for enterprise Veeam admins.

Two components:

1. **Engine** — calculates repository footprint, proxy requirements, SOBR layout, WAN/RPO performance, risk scoring, cost modeling, replication, NAS, WAN acceleration, licensing, tape, compliance, and more — from a YAML project file.
2. **Web UI** — FastAPI + Jinja2 interface with a guided form, workload type tabs, interactive dashboard, and downloadable HTML report.

---

## What's new in v3.0.0

- **Form UX overhaul** — datalist dropdowns for common values, pre-populated defaults, workload type tabs (VM / NAS / Physical / Replication)
- **Replication sizing** — replica storage TB, CDP proxy + journal sizing, WAN feasibility
- **NAS/Unstructured sizing** — file proxy cores + RAM, cache repo, GFS retention
- **WAN Accelerator** (`wan_accel.py`) — source/target appliance count, cache sizing, effective throughput with dedupe × compress, backup copy job window validation
- **Veeam VUL License Estimator** (`licensing.py`) — total workload count, community / standard / enterprise tier, annual list-price estimate
- **LTO Tape Library Sizing** (`tape.py`) — LTO-7/8/9 cartridge and scratch pool, slot and drive count, annual media cost
- **Veeam ONE + Enterprise Manager** (`veeam_one.py`) — tiered server/RAM/DB sizing by workload count, EM and VSPC headroom
- **Compliance Gap Analysis** (`compliance.py`) — HIPAA, SOC 2, GDPR, PCI DSS, DORA framework checks against your current config
- **Downloadable HTML Report** — self-contained, print-ready report covering all sites, all modules, compliance status, and cost comparison (`/export/report`)
- **REST API** — `POST /api/design`, `GET /api/health`, `GET /api/profiles`
- **Pytest suite** — 12 test modules covering every engine component

---

## Project Structure

```
veeam_designer/       # Core engine package
  sizing.py           # Multi-site orchestration
  models.py           # All dataclasses (VeeamInput, VeeamDesign, ...)
  roles.py            # Proxy + backup server sizing
  nas.py              # NAS/unstructured workload sizing
  replication.py      # VM replication + CDP sizing
  agent.py            # Physical/agent backup sizing
  wan_accel.py        # WAN accelerator + BCJ sizing
  licensing.py        # Veeam VUL license estimator
  tape.py             # LTO tape library sizing
  veeam_one.py        # Veeam ONE + EM + VSPC sizing
  compliance.py       # Regulatory framework gap analysis
  sobr.py             # SOBR / capacity tier design
  cost.py             # 3-year TCO + cloud comparison
  risk.py             # Risk scoring engine
  orca.py             # ObjectFirst Orca node sizing
  network.py          # WAN/RPO feasibility
  repo_perf.py        # Repo throughput modeling
  parser.py           # YAML/JSON project file loader
  cli.py              # CLI entry point
ui/
  main.py             # FastAPI app + REST API + export routes
  templates/
    index.html        # Web UI (form + dashboard)
    report.html       # Downloadable HTML report template
config.json           # Engine tuning parameters
profiles.json         # MSP / SMB / Enterprise / Dedupe presets
pyproject.toml        # Package metadata (veeam-designer 3.0.0)
example-project.yml   # Reference project file
tests/                # 12-module pytest suite
```

---

## Installation

### 1. Create a virtual environment

**Windows**
```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS**
```bash
python -m venv venv
source venv/bin/activate
```

### 2. Install

```bash
# Engine only
pip install -e .

# Engine + Web UI
pip install -e ".[web]"

# Engine + Web UI + dev tools (flake8, pytest, httpx)
pip install -e ".[web,dev]"
```

---

## Web UI

```bash
uvicorn ui.main:app --reload
```

Open: `http://127.0.0.1:8000/run`

### Workload Type Tabs

The form has four tabs — select the one that matches your workload before clicking **Run design**:

| Tab | Use for |
|---|---|
| **VM Backup** | VMware / Hyper-V / AHV virtual machine backups |
| **NAS** | File shares, NAS filers, unstructured data |
| **Physical** | Bare-metal servers, agent-based backups |
| **Replication** | VM replication jobs + CDP (near-zero RPO) |

### Form Features

- Datalist dropdowns for common values (data size, churn rate, retention, WAN bandwidth, etc.) — all fields remain manually typeable
- Pre-populated defaults so nothing starts blank
- Per-site GFS retention, advanced SOBR / capacity tier, compliance framework selection
- Replication sub-section: RPO, WAN, CDP toggle
- NAS sub-section: share count, file count, object storage toggle

### Outputs

After running, the dashboard shows:

- **Infrastructure** — repo breakdown (primary + GFS + capacity tier), proxy count/cores/RAM, backup server specs
- **Replication** — replica storage TB, CDP proxy cores + journal TB, WAN feasibility
- **NAS** — cache repo, primary repo, file proxy specs
- **WAN Accelerator** — appliance count, cache per source, effective throughput, BCJ window pass/fail
- **Licensing** — protected workload count, tier, estimated annual cost
- **Tape** — cartridge count, drives, slots, annual media cost
- **Veeam ONE** — server and DB sizing, EM and VSPC specs
- **Compliance** — framework badge (compliant / partial / non-compliant), gap list
- **Cost** — yearly on-prem, yearly object, 3-year TCO, break-even
- **Risk** — score and level with per-factor breakdown

### Export

- **Export CSV** — `/export/csv` — dashboard data in spreadsheet format
- **Download Report** — `/export/report` — self-contained HTML report, no internet required, print-to-PDF ready

---

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | `{"status": "ok", "version": "3.0.0"}` |
| `GET` | `/api/profiles` | List available profile names |
| `POST` | `/api/design` | Accept YAML body (`text/plain`), return full JSON design |

### Example

```bash
curl -X POST http://localhost:8000/api/design \
  -H "Content-Type: text/plain" \
  --data-binary @project.yml
```

---

## CLI

```bash
# Run with a project file
veeam-designer --project-file project.yml

# JSON output (used by the UI and REST API)
veeam-designer --project-file project.yml --json

# Interactive mode
veeam-designer
```

---

## YAML Project Format

```yaml
profile: enterprise          # smb | msp | enterprise | dedupe
compliance_framework: hipaa  # none | hipaa | soc2 | gdpr | pci_dss | dora

sites:
  - name: Primary DC
    veeam_input:
      total_data_tb: 500
      annual_growth_percent: 15
      daily_change_percent: 5
      backup_type: synthetic_full_weekly
      primary_retention_days: 30
      gfs_weekly_count: 4
      gfs_monthly_count: 12
      gfs_yearly_count: 3
      backup_window_hours: 8
      target_rpo_hours: 4
      vm_count: 800
      avg_vm_size_gb: 400
      wan_bandwidth_mbps: 1000
      repo_type: sobr
      hypervisor: vmware
      has_san_access: true
      immutability_enabled: true
      capacity_tier_enabled: true

      # Replication sub-section (optional)
      replication:
        source_tb: 50
        vm_count: 100
        wan_mbps: 1000
        rpo_hours: 1.0
        cdp_enabled: false

      # NAS sub-section (optional)
      nas:
        source_tb: 100
        share_count: 50
        retention_days: 30
        immutability_enabled: true

      # Tape archive (optional)
      tape:
        archive_tb: 200
        lto_generation: 9
        retention_years: 7
```

---

## New Engine Modules (v3.0.0)

### WAN Accelerator (`wan_accel.py`)

Sizes source and target WAN accelerator appliances and validates backup copy job window.

```python
from veeam_designer.models import WanAccelInput
from veeam_designer.wan_accel import size_wan_accel

result = size_wan_accel(WanAccelInput(source_tb=200, wan_mbps=100, dedupe_ratio=3.0))
# result.source_appliance_count, result.effective_mbps, result.meets_copy_window
```

### License Estimator (`licensing.py`)

Counts protected workloads and estimates Veeam VUL annual cost.

```python
from veeam_designer.models import LicenseInput
from veeam_designer.licensing import estimate_license

result = estimate_license(LicenseInput(vm_count=400, nas_tb=50, physical_count=10))
# result.tier ("standard"), result.annual_maintenance_usd
```

### Tape Sizing (`tape.py`)

LTO-7, LTO-8, or LTO-9 library sizing with scratch pool and slot allocation.

```python
from veeam_designer.models import TapeInput
from veeam_designer.tape import size_tape

result = size_tape(TapeInput(archive_tb=300, lto_generation=9, retention_years=7))
# result.cartridge_count, result.drive_count_recommended, result.library_slots_needed
```

### Veeam ONE + EM (`veeam_one.py`)

Tiered server + RAM + database sizing, Enterprise Manager and VSPC headroom.

```python
from veeam_designer.models import VeeamOneInput
from veeam_designer.veeam_one import size_veeam_one

result = size_veeam_one(VeeamOneInput(protected_vms=2000, enterprise_manager=True, vspc_tenants=50))
# result.server_cores, result.server_ram_gb, result.em_cores, result.vspc_cores
```

### Compliance (`compliance.py`)

Gap analysis against HIPAA, SOC 2, GDPR, PCI DSS, or DORA.

```python
from veeam_designer.models import ComplianceInput
from veeam_designer.compliance import check_compliance

result = check_compliance(ComplianceInput(
    framework="hipaa",
    current_retention_days=365,
    immutability_enabled=True,
    encryption_enabled=True,
    offsite_copy_enabled=True,
))
# result.compliant, result.gaps, result.risk_level
```

---

## Tests

```bash
pip install -e ".[web,dev]"
pytest tests/ -v
```

12 test modules: `test_vm_sizing`, `test_nas_sizing`, `test_replication`, `test_agent`, `test_wan_accel`, `test_licensing`, `test_tape`, `test_veeam_one`, `test_compliance`, `test_risk`, `test_cost`, `test_api`.

---

## Configuration

**`config.json`** — engine tuning (throughput per core, overhead factors, cost rates, VUL price, etc.)

**`profiles.json`** — preset ratio and retention overrides per profile:

| Profile | Best for |
|---|---|
| `smb` | Small business, 12 MB/s/core |
| `enterprise` | Large environment, higher warn thresholds |
| `msp` | Multi-tenant, 3 tasks/core |
| `dedupe` | Dedupe appliance targets |

---

## Docker

### Docker Hub

```bash
docker pull emb079/veeam-designer
docker run -p 8000:8000 emb079/veeam-designer
```

[hub.docker.com/r/emb079/veeam-designer](https://hub.docker.com/r/emb079/veeam-designer)

### GitHub Container Registry

```bash
docker pull ghcr.io/eblackrps/veeam-designer
docker run -p 8000:8000 ghcr.io/eblackrps/veeam-designer
```

[ghcr.io/eblackrps/veeam-designer](https://github.com/eblackrps/veeam_designer/pkgs/container/veeam-designer)

### docker-compose

```bash
docker-compose up
```

Open `http://localhost:8000/run`.

### Mount custom config

```bash
docker run -p 8000:8000 \
  -v ./config.json:/app/config.json \
  -v ./profiles.json:/app/profiles.json \
  emb079/veeam-designer
```

---

## Troubleshooting

**`ModuleNotFoundError: python-multipart`**
```bash
pip install python-multipart
```

**`ModuleNotFoundError: httpx`** (tests only)
```bash
pip install -e ".[web,dev]"
```

**No output from the engine**
Ensure at least one checkbox (Blueprint, Cost) is selected before clicking Run.

**Docker push fails with `unauthorized`**
Ensure `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets are set in GitHub → Settings → Secrets. The token needs Read, Write, Delete scope.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).

© E. Black
