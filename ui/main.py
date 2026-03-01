from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

# Project root: ...\veeam-designer-final-with-ui
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "ui" / "templates"

app = FastAPI(title="Veeam Designer UI")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

LAST_DASHBOARD_DATA: Optional[Dict[str, Any]] = None


def run_cli_with_json(project_file: Path) -> Dict[str, Any]:
    """
    Run veeam_designer.cli with --project-file and --json and return parsed JSON.
    """
    python_exe = sys.executable or "python"

    cmd = [
        python_exe,
        "-m",
        "veeam_designer.cli",
        "--project-file",
        str(project_file),
        "--json",
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(BASE_DIR),
    )

    if proc.returncode != 0:
        raise RuntimeError(f"CLI failed: {proc.stderr.strip() or proc.stdout.strip()}")

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Failed to parse CLI JSON output: {exc}\nRaw: {proc.stdout[:500]}"
        )


def build_dashboard_from_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a compact summary for the visual environment dashboard.
    """
    # Import here to avoid circular import at module level
    from veeam_designer.roles import TRANSPORT_MB_PER_CORE

    sites_summary: List[Dict[str, Any]] = []

    total_repo_tb = data.get("total_repo_tb")
    notes = data.get("notes") or {}
    sobr_note = notes.get("sobr")

    for site_obj in data.get("sites", []):
        name = site_obj.get("name", "Unknown")
        design = site_obj.get("design", {})

        repo = design.get("repo", {})
        roles = design.get("roles", {})
        proxies = roles.get("proxies", {})
        backup_server = roles.get("backup_server", {})
        network = design.get("network", {})
        risk = design.get("risk", {})
        repo_perf = design.get("repo_perf", {})
        cost = design.get("cost", {})
        sobr = design.get("sobr", {})
        orca = design.get("orca")
        replication = design.get("replication")
        nas = design.get("nas")
        wan_accel = design.get("wan_accel")
        license_estimate = design.get("license_estimate")
        tape = design.get("tape")
        veeam_one = design.get("veeam_one")
        compliance = design.get("compliance")

        total_repo = float(repo.get("total_repo_tb", 0.0))
        primary_repo = float(repo.get("primary_repo_tb", 0.0))
        gfs_repo = float(repo.get("gfs_repo_tb", 0.0))
        capacity_tier_tb = float(sobr.get("capacity_tier_tb", 0.0))

        proxy_count = int(proxies.get("proxy_count", 0))
        total_proxy_cores = int(proxies.get("total_proxy_cores", 0))
        proxy_ram_gb = int(proxies.get("total_proxy_ram_gb", 0))
        transport_mode = proxies.get("transport_mode", "auto")

        bs_cores = int(backup_server.get("cores", 0))
        bs_ram_gb = int(backup_server.get("ram_gb", 0))

        required_mb_s = float(repo_perf.get("required_mb_s", 0.0))
        mb_per_core = TRANSPORT_MB_PER_CORE.get(transport_mode, 15.0)
        proxy_capacity_mb_s = total_proxy_cores * mb_per_core
        proxy_load_ratio = (
            required_mb_s / proxy_capacity_mb_s if proxy_capacity_mb_s > 0 else 0.0
        )

        wan_required_mbps = float(network.get("required_mbps", 0.0))
        wan_meets_target = bool(network.get("meets_target", False))

        risk_level = risk.get("level", "unknown")
        risk_score = int(risk.get("total_score", 0))
        risk_details = risk.get("details", {})

        yearly_onprem_usd = float(cost.get("yearly_onprem_usd", 0.0))
        monthly_object_usd = float(cost.get("monthly_object_usd", 0.0))
        cloud_comparison = cost.get("cloud_comparison", {})
        three_year_tco = cost.get("three_year_tco", {})
        break_even_years = float(cost.get("break_even_years", 0.0))

        sites_summary.append(
            {
                "name": name,
                "total_repo_tb": total_repo,
                "primary_repo_tb": primary_repo,
                "gfs_repo_tb": gfs_repo,
                "capacity_tier_tb": capacity_tier_tb,
                "proxy_count": proxy_count,
                "total_proxy_cores": total_proxy_cores,
                "proxy_ram_gb": proxy_ram_gb,
                "transport_mode": transport_mode,
                "bs_cores": bs_cores,
                "bs_ram_gb": bs_ram_gb,
                "required_mb_s": required_mb_s,
                "proxy_capacity_mb_s": proxy_capacity_mb_s,
                "proxy_load_ratio": proxy_load_ratio,
                "wan_required_mbps": wan_required_mbps,
                "wan_meets_target": wan_meets_target,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "risk_details": risk_details,
                "yearly_onprem_usd": yearly_onprem_usd,
                "monthly_object_usd": monthly_object_usd,
                "cloud_comparison": cloud_comparison,
                "three_year_tco": three_year_tco,
                "break_even_years": break_even_years,
                "orca": orca,
                "replication": replication,
                "nas": nas,
                "wan_accel": wan_accel,
                "license_estimate": license_estimate,
                "tape": tape,
                "veeam_one": veeam_one,
                "compliance": compliance,
            }
        )

    return {
        "total_repo_tb": total_repo_tb,
        "sobr_note": sobr_note,
        "sites": sites_summary,
    }


def build_csv_from_dashboard(dashboard: Dict[str, Any]) -> str:
    """Build a simple CSV representation of the dashboard sites."""
    headers = [
        "site",
        "total_repo_tb",
        "primary_repo_tb",
        "gfs_repo_tb",
        "proxy_count",
        "total_proxy_cores",
        "required_mb_s",
        "proxy_capacity_mb_s",
        "proxy_load_ratio",
        "wan_required_mbps",
        "wan_meets_target",
        "risk_level",
        "risk_score",
        "yearly_onprem_usd",
        "monthly_object_usd",
    ]
    lines: List[str] = []
    lines.append(",".join(headers))

    for site in dashboard.get("sites", []):
        def fmt(val: Any) -> str:
            if isinstance(val, float):
                return f"{val:.2f}"
            return str(val)

        row = [
            fmt(site.get("name", "")),
            fmt(site.get("total_repo_tb", 0.0)),
            fmt(site.get("primary_repo_tb", 0.0)),
            fmt(site.get("gfs_repo_tb", 0.0)),
            fmt(site.get("proxy_count", 0)),
            fmt(site.get("total_proxy_cores", 0)),
            fmt(site.get("required_mb_s", 0.0)),
            fmt(site.get("proxy_capacity_mb_s", 0.0)),
            fmt(site.get("proxy_load_ratio", 0.0)),
            fmt(site.get("wan_required_mbps", 0.0)),
            "yes" if site.get("wan_meets_target") else "no",
            fmt(site.get("risk_level", "")),
            fmt(site.get("risk_score", 0)),
            fmt(site.get("yearly_onprem_usd", 0.0)),
            fmt(site.get("monthly_object_usd", 0.0)),
        ]
        lines.append(",".join(row))

    return "\n".join(lines)


def render_blueprint_human(data: Dict[str, Any]) -> str:
    """
    Render a human-readable multi-site blueprint summary from JSON.
    """
    lines: List[str] = []

    total_repo_tb = data.get("total_repo_tb")
    notes = data.get("notes") or {}
    sobr_note = notes.get("sobr")

    if total_repo_tb is not None:
        lines.append(f"Multi-site repo footprint: {total_repo_tb:.1f} TB total")
    if sobr_note:
        lines.append(f"- Note [sobr]: {sobr_note}")
    lines.append("")
    lines.append("Per-site blueprint summary:")

    for site_obj in data.get("sites", []):
        name = site_obj.get("name", "Unknown")
        design = site_obj.get("design", {})

        repo = design.get("repo", {})
        roles = design.get("roles", {})
        proxies = roles.get("proxies", {})
        hardened = roles.get("hardened_repos", {})
        sobr = design.get("sobr", {})
        repo_perf = design.get("repo_perf", {})
        network = design.get("network", {})
        risk = design.get("risk", {})

        lines.append(f"== {name} ==")
        lines.append(
            f"- Repo: {repo.get('total_repo_tb', 0):.1f} TB "
            f"(primary {repo.get('primary_repo_tb', 0):.1f} TB, "
            f"GFS {repo.get('gfs_repo_tb', 0):.1f} TB)"
        )
        lines.append(
            f"- Proxies: {proxies.get('proxy_count', 0)} "
            f"({proxies.get('total_proxy_cores', 0)} cores, "
            f"{proxies.get('total_parallel_tasks', 0)} tasks)"
        )

        if hardened:
            lines.append(
                f"- Hardened repos: {hardened.get('count', 0)} hosts, "
                f"~{hardened.get('tb_per_host', 0):.1f} TB per host"
            )

        if sobr:
            lines.append(
                f"- SOBR: {sobr.get('extent_count', 0)} extents @ ~{sobr.get('extent_size_tb', 0):.1f} TB each"
            )

        if repo_perf:
            lines.append(
                f"- Repo perf: required {repo_perf.get('required_mb_s', 0):.1f} MB/s, "
                f"synthetic full {repo_perf.get('synthetic_full_mb_s', 0):.1f} MB/s"
            )

        if network:
            lines.append(
                f"- Network: requires {network.get('required_mbps', 0):.1f} Mbps, "
                f"meets target: {network.get('meets_target', False)}"
            )

        if risk:
            details = risk.get("details", {})
            lines.append(
                f"- Risk: {risk.get('level', 'unknown')} (score {risk.get('total_score', 0)}, "
                f"repo={details.get('repo', 0)}, wan={details.get('wan', 0)}, proxies={details.get('proxies', 0)})"
            )

        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_cost_human(data: Dict[str, Any]) -> str:
    """
    Render cost summary from the same JSON payload.
    """
    lines: List[str] = []

    sites = data.get("sites", [])
    if not sites:
        return "No site data available for cost output.\n"

    total_onprem = 0.0
    total_object = 0.0

    lines.append(
        "Total repo across all sites: "
        f"{data.get('total_repo_tb', 0):.1f} TB"
    )
    lines.append("")
    lines.append("Per-site cost breakdown:")

    for site_obj in sites:
        name = site_obj.get("name", "Unknown")
        design = site_obj.get("design", {})
        repo = design.get("repo", {})
        cost = design.get("cost", {})

        total_repo_tb = float(repo.get("total_repo_tb", 0.0))
        yearly_onprem = float(cost.get("yearly_onprem_usd", 0.0))
        yearly_object = float(cost.get("monthly_object_usd", 0.0)) * 12.0

        total_onprem += yearly_onprem
        total_object += yearly_object

        lines.append(f"== {name} ==")
        lines.append(f"- Total repo: {total_repo_tb:.1f} TB")
        lines.append(f"- Yearly on-prem cost: ${yearly_onprem:,.0f}")
        lines.append(f"- Yearly object cost:  ${yearly_object:,.0f}")
        lines.append("")

    lines.append("Aggregated cost:")
    lines.append(f"- Total yearly on-prem: ${total_onprem:,.0f}")
    lines.append(f"- Total yearly object:  ${total_object:,.0f}")
    lines.append("")

    return "\n".join(lines)


def get_default_yaml() -> str:
    """
    Default YAML shown in the editor if nothing has been posted yet.
    """
    example = BASE_DIR / "example-project.yml"
    if example.exists():
        return example.read_text(encoding="utf-8")

    return (
        "profile: msp\n"
        "sites:\n"
        "  - name: HQ\n"
        "    veeam_input:\n"
        "      total_data_tb: 200\n"
        "      annual_growth_percent: 15\n"
        "      daily_change_percent: 5\n"
        "      backup_type: synthetic_full_weekly\n"
        "      primary_retention_days: 30\n"
        "      gfs_weekly_count: 4\n"
        "      gfs_monthly_count: 12\n"
        "      gfs_yearly_count: 3\n"
        "      backup_window_hours: 8\n"
        "      target_rpo_hours: 24\n"
        "      vm_count: 600\n"
        "      avg_vm_size_gb: 250\n"
        "      wan_bandwidth_mbps: 500\n"
        "      repo_type: sobr\n"
        "      hypervisor: vmware\n"
        "      has_san_access: true\n"
        "      on_host_proxy: true\n"
    )


@app.get("/", response_class=HTMLResponse)
async def root() -> RedirectResponse:
    """
    Redirect base URL to /run.
    """
    return RedirectResponse(url="/run")


@app.get("/export/csv")
async def export_csv() -> PlainTextResponse:
    """
    Export the most recent dashboard as CSV.
    """
    if LAST_DASHBOARD_DATA is None:
        raise HTTPException(status_code=400, detail="No dashboard data available. Run a design first.")

    csv_text = build_csv_from_dashboard(LAST_DASHBOARD_DATA)
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=veeam-designer-dashboard.csv"},
    )


@app.get("/export/report")
async def export_report(request: Request):
    """Download a self-contained HTML design report."""
    if LAST_DASHBOARD_DATA is None:
        raise HTTPException(status_code=400, detail="No dashboard data available. Run a design first.")
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html_content = templates.TemplateResponse(
        "report.html",
        {"request": request, "dashboard": LAST_DASHBOARD_DATA, "generated_at": generated_at},
    ).body.decode("utf-8")
    return PlainTextResponse(
        content=html_content,
        media_type="text/html",
        headers={"Content-Disposition": "attachment; filename=veeam-design-report.html"},
    )


@app.get("/run", response_class=HTMLResponse)
async def get_run(request: Request) -> HTMLResponse:
    yaml_content = get_default_yaml()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "yaml_content": yaml_content,
            "blueprint_output": None,
            "cost_output": None,
            "dashboard": None,
        },
    )


@app.post("/run", response_class=HTMLResponse)
async def post_run(
    request: Request,
    yaml_content: str = Form(...),
    run_blueprint: Optional[str] = Form(None),
    run_cost: Optional[str] = Form(None),
) -> HTMLResponse:
    blueprint_output: Optional[str] = None
    cost_output: Optional[str] = None
    dashboard: Optional[Dict[str, Any]] = None

    run_blueprint_flag = run_blueprint is not None
    run_cost_flag = run_cost is not None

    if not (run_blueprint_flag or run_cost_flag):
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "yaml_content": yaml_content,
                "blueprint_output": None,
                "cost_output": None,
                "dashboard": None,
            },
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "project.yml"
        tmp_path.write_text(yaml_content, encoding="utf-8")

        try:
            data = run_cli_with_json(tmp_path)
        except Exception as exc:
            error_msg = f"Error running design: {exc}"
            if run_blueprint_flag:
                blueprint_output = error_msg
            if run_cost_flag:
                cost_output = error_msg
        else:
            if run_blueprint_flag:
                blueprint_output = render_blueprint_human(data)
                dashboard = build_dashboard_from_json(data)
                global LAST_DASHBOARD_DATA
                LAST_DASHBOARD_DATA = dashboard
            if run_cost_flag:
                cost_output = render_cost_human(data)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "yaml_content": yaml_content,
            "blueprint_output": blueprint_output,
            "cost_output": cost_output,
            "dashboard": dashboard,
        },
    )
