# Veeam Designer + Web UI

This project provides two major components:

1. **Veeam Designer Engine**  
   A multi-site Veeam sizing system that calculates repository footprint, proxy requirements, SOBR layout, WAN/RPO performance, risk scoring, and cost modeling.

2. **Web UI**  
   A FastAPI + Jinja + Tailwind interface that:
   - Builds YAML project files using a clean multi-site form  
   - Runs Blueprint & Cost using the engine  
   - Displays results directly in the browser  
   - Allows direct YAML editing for power users  

---

## 1. Project Structure

Your folder should contain:

```
veeam_designer/
ui/
config.json
profiles.json
pyproject.toml
```

Optional:

```
example-project.yml
```

---

## 2. Installation

### Create a virtual environment

**Windows**
```powershell
python -m venv venv
.
env\Scripts ctivate
```

**Linux/macOS**
```bash
python -m venv venv
source venv/bin/activate
```

### Install dependencies

```bash
pip install -e .
pip install uvicorn fastapi jinja2 python-multipart
```

Note: The flat-package warning (“multiple top-level packages discovered”) is normal.

---

## 3. Start the Web UI

```bash
uvicorn ui.main:app --reload
```

Then open:

```
http://127.0.0.1:8000/run
```

---

## 4. UI Overview

Two modes are available:

### **Simple Form Mode**
Guided interface for entering site details and global settings.

### **YAML Mode**
Allows copying/pasting or editing project YAML directly.

---

## 5. Global Settings

- **Profile** (MSP, SMB, Enterprise, Custom)  
- **Hypervisor** (VMware, Hyper-V, AHV, Physical, Mixed)  
- **Target RPO (hours)**  
- **Compression ratio** (optional override)  
- **Dedupe ratio** (optional override)

---

## 6. Site Configuration

Each site includes:

- Name  
- Total data (TB)  
- Annual growth (%)  
- Daily change (%)  
- Primary retention (days)  
- VM count  
- Average VM size (GB)  
- WAN bandwidth (Mbps)  
- Backup window (hours)  

Site 2 may be disabled entirely.

---

## 7. Advanced Per-Site Options

### GFS Retention
- Toggle to enable or disable  
- Weekly / Monthly / Yearly values  

### Backup Type
- Synthetic full weekly  
- Forever forward incremental  
- Reverse incremental  

### Repo Type
- SOBR  
- Direct repo  
- Object  

### Transport Options
- DirectSAN  
- On-host HotAdd  

---

## 8. Running Blueprint & Cost Models

Select **Blueprint**, **Cost**, or both.  
Click **Run design**.

The UI will:

1. Generate YAML  
2. Write a temp file  
3. Execute the engine  
4. Display output

Outputs include repo sizing, proxies, SOBR layouts, WAN performance, risks, and cost breakdowns.

---

## 9. Troubleshooting

### Missing `python-multipart`
Install it:

```bash
pip install python-multipart
```

### No output
Ensure at least one checkbox (Blueprint, Cost) is selected.

---

## 10. CLI Usage

Run directly:

```bash
python -m veeam_designer.cli --project-file project.yml --json
```

Or interactive:

```bash
python -m veeam_designer.cli
```

---

## 11. Attribution

© E. Black  
Built to simplify Veeam sizing and architecture workflows.
