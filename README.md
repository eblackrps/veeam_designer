# Veeam Designer

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Release](https://img.shields.io/github/v/release/eblackrps/veeam_designer)

A multi-site Veeam backup environment sizing and architecture tool.

Two components:

1. **Engine** — calculates repository footprint, proxy requirements, SOBR layout, WAN/RPO performance, risk scoring, and cost modeling from a YAML project file.
2. **Web UI** — FastAPI + Jinja2 interface for building project files, running the engine, and viewing results in the browser.

---

## Project Structure

```
veeam_designer/   # Core engine package
ui/               # FastAPI web interface
config.json       # Engine tuning parameters
profiles.json     # MSP / SMB / Enterprise presets
pyproject.toml    # Package metadata
example-project.yml
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

### 2. Install the engine

```bash
pip install -e .
```

### 3. Install web UI dependencies

```bash
pip install -e ".[web]"
```

Or manually:
```bash
pip install fastapi uvicorn jinja2 python-multipart
```

---

## Web UI

Start the server:

```bash
uvicorn ui.main:app --reload
```

Open: `http://127.0.0.1:8000/run`

### Simple Form Mode
Guided interface for entering site details and global settings.

### YAML Mode
Copy/paste or directly edit the project YAML.

---

## Global Settings

| Setting | Options |
|---|---|
| Profile | MSP, SMB, Enterprise, Custom |
| Hypervisor | VMware, Hyper-V, AHV, Physical, Mixed |
| Target RPO | hours |
| Compression ratio | optional override |
| Dedupe ratio | optional override |

---

## Site Configuration

Each site supports:

- Name, total data (TB), annual growth (%), daily change rate (%)
- Primary retention (days), VM count, average VM size (GB)
- WAN bandwidth (Mbps), backup window (hours)

Up to two sites. Site 2 can be disabled.

---

## Advanced Per-Site Options

### GFS Retention
Enable/disable with weekly / monthly / yearly values.

### Backup Type
- Synthetic full weekly
- Forever forward incremental
- Reverse incremental

### Repo Type
- SOBR
- Direct repo
- Object storage

### Transport
- DirectSAN
- On-host HotAdd

---

## Running the Engine

### Via Web UI
Select **Blueprint**, **Cost**, or both, then click **Run design**.

### Via CLI

```bash
# With a project file
veeam-designer --project-file project.yml

# JSON output
veeam-designer --project-file project.yml --json

# Interactive mode
veeam-designer
```

---

## Outputs

- Repository sizing per site
- Proxy count and core requirements
- SOBR layout and tier recommendations
- WAN performance and RPO feasibility
- Risk scoring
- Cost breakdown (on-prem vs. object storage)

---

## Configuration

`config.json` holds tuning parameters (throughput per core, overhead factors, cost rates, etc.). Edit to match your environment. All values must be valid JSON.

`profiles.json` holds preset ratio and retention values for each profile type.

---

## Troubleshooting

**`ModuleNotFoundError: python-multipart`**
```bash
pip install python-multipart
```

**No output from the engine**
Ensure at least one checkbox (Blueprint, Cost) is selected before clicking Run.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).

© E. Black
