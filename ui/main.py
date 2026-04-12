from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import uvicorn
from fastapi import Body, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from veeam_designer._version import __version__
from veeam_designer.config import load_profiles
from veeam_designer.service import design_payload_from_project_text

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "ui" / "templates"
STATIC_DIR = BASE_DIR / "ui" / "static"
EXAMPLE_PROJECT = BASE_DIR / "example-project.yml"
MAX_PROJECT_TEXT_BYTES = 1_048_576

app = FastAPI(title="Veeam Designer", version=__version__)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

LAST_RESULT_PAYLOAD: Optional[dict[str, Any]] = None
LAST_DASHBOARD_DATA: Optional[dict[str, Any]] = None


def get_default_project_text() -> str:
    """Return the default YAML shown in the editor."""

    if EXAMPLE_PROJECT.exists():
        return EXAMPLE_PROJECT.read_text(encoding="utf-8")

    return (
        "profile: enterprise\n"
        "sites:\n"
        "  - name: Primary DC\n"
        "    veeam_input:\n"
        "      total_data_tb: 500\n"
        "      daily_change_percent: 5\n"
        "      backup_window_hours: 8\n"
    )


def load_profile_names() -> list[str]:
    """Return available sizing profiles for the UI."""

    profiles = load_profiles()
    names = sorted(profiles.keys())
    return names if names else ["enterprise", "msp", "smb", "dedupe"]


def build_csv_from_payload(payload: dict[str, Any]) -> str:
    """Flatten a result payload into a generic key/value CSV export."""

    rows = ["field,value"]
    for field, value in _flatten_mapping(payload).items():
        rows.append(f"{_csv_escape(field)},{_csv_escape(str(value))}")
    return "\n".join(rows) + "\n"


def build_dashboard_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Build a dashboard summary for VM-oriented outputs."""

    kind = payload.get("kind")
    if kind == "multi-site":
        notes = payload.get("notes") or {}
        return {
            "kind": "multi-site",
            "total_repo_tb": float(payload.get("total_repo_tb", 0.0)),
            "sobr_note": notes.get("sobr"),
            "sites": [
                _build_dashboard_site(site.get("design", {}), site.get("name", "Site"))
                for site in payload.get("sites", [])
            ],
        }

    if kind == "vm":
        notes = payload.get("notes") or {}
        return {
            "kind": "vm",
            "total_repo_tb": float((payload.get("repo") or {}).get("total_repo_tb", 0.0)),
            "sobr_note": notes.get("sobr"),
            "sites": [_build_dashboard_site(payload, "Current Design")],
        }

    return None


def render_blueprint_human(payload: dict[str, Any]) -> str:
    """Render a concise operator-facing blueprint summary."""

    kind = payload.get("kind")
    if kind in {"multi-site", "vm"}:
        return _render_vm_blueprint(payload)
    if kind == "nas":
        result = payload.get("result") or {}
        return (
            "NAS / unstructured sizing\n"
            f"- Total repository: {float(result.get('total_repo_tb', 0.0)):.1f} TB\n"
            f"- Cache repository: {float(result.get('cache_repo_tb', 0.0)):.1f} TB\n"
            f"- File proxy sizing: {int(result.get('file_proxy_cores', 0))} cores / "
            f"{int(result.get('file_proxy_ram_gb', 0))} GB RAM\n"
        )
    if kind == "physical":
        result = payload.get("result") or {}
        return (
            "Physical / agent sizing\n"
            f"- Total repository: {float(result.get('total_repo_tb', 0.0)):.1f} TB\n"
            f"- Coordinator sizing: {int(result.get('coordinator_cores', 0))} cores / "
            f"{int(result.get('coordinator_ram_gb', 0))} GB RAM\n"
        )
    if kind == "replication":
        result = payload.get("result") or {}
        return (
            "Replication sizing\n"
            f"- Required bandwidth: {float(result.get('required_mbps', 0.0)):.1f} Mbps\n"
            f"- Replica storage: {float(result.get('replica_storage_tb', 0.0)):.1f} TB\n"
            f"- Meets target RPO: {'yes' if result.get('meets_rpo') else 'no'}\n"
        )
    return "No design output available.\n"


def render_cost_human(payload: dict[str, Any]) -> str:
    """Render a compact cost summary."""

    kind = payload.get("kind")
    if kind == "multi-site":
        total_on_prem = 0.0
        total_object = 0.0
        lines = ["Cost overview"]
        for site in payload.get("sites", []):
            design = site.get("design") or {}
            cost = design.get("cost") or {}
            yearly_on_prem = float(cost.get("yearly_onprem_usd", 0.0))
            monthly_object = float(cost.get("monthly_object_usd", 0.0))
            total_on_prem += yearly_on_prem
            total_object += monthly_object * 12.0
            lines.append(
                f"- {site.get('name', 'Site')}: "
                f"on-prem ${yearly_on_prem:,.0f}/yr, "
                f"object ${monthly_object * 12.0:,.0f}/yr"
            )
        lines.append(f"- Total on-prem: ${total_on_prem:,.0f}/yr")
        lines.append(f"- Total object: ${total_object:,.0f}/yr")
        return "\n".join(lines) + "\n"

    if kind == "vm":
        cost = payload.get("cost") or {}
        return (
            "Cost overview\n"
            f"- On-prem yearly estimate: ${float(cost.get('yearly_onprem_usd', 0.0)):,.0f}\n"
            f"- Object storage yearly estimate: ${float(cost.get('yearly_object_usd', 0.0)):,.0f}\n"
            f"- Break-even vs cloud: {float(cost.get('break_even_years', 0.0)):.1f} years\n"
        )

    return "Cost projection is not generated for this calculator mode.\n"


def build_result_summary(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Build headline metrics for the web dashboard."""

    kind = payload.get("kind")
    if kind == "multi-site":
        return [
            {"label": "Sites", "value": str(len(payload.get("sites", [])))},
            {"label": "Repository", "value": f"{float(payload.get('total_repo_tb', 0.0)):.1f} TB"},
            {
                "label": "Yearly Cost",
                "value": f"${sum(float((site.get('design', {}).get('cost', {}) or {}).get('yearly_onprem_usd', 0.0)) for site in payload.get('sites', [])):,.0f}",
            },
        ]
    if kind == "vm":
        repo = payload.get("repo") or {}
        roles = payload.get("roles") or {}
        cost = payload.get("cost") or {}
        proxies = roles.get("proxies") or {}
        return [
            {"label": "Repository", "value": f"{float(repo.get('total_repo_tb', 0.0)):.1f} TB"},
            {"label": "Proxy Count", "value": str(int(proxies.get("proxy_count", 0)))},
            {"label": "Yearly Cost", "value": f"${float(cost.get('yearly_onprem_usd', 0.0)):,.0f}"},
        ]
    if kind == "nas":
        result = payload.get("result") or {}
        return [
            {"label": "Repository", "value": f"{float(result.get('total_repo_tb', 0.0)):.1f} TB"},
            {"label": "File Proxies", "value": str(int(result.get("file_proxy_cores", 0)))},
            {"label": "Cache Repo", "value": f"{float(result.get('cache_repo_tb', 0.0)):.1f} TB"},
        ]
    if kind == "physical":
        result = payload.get("result") or {}
        return [
            {"label": "Repository", "value": f"{float(result.get('total_repo_tb', 0.0)):.1f} TB"},
            {"label": "Coordinator Cores", "value": str(int(result.get("coordinator_cores", 0)))},
            {"label": "Coordinator RAM", "value": f"{int(result.get('coordinator_ram_gb', 0))} GB"},
        ]
    if kind == "replication":
        result = payload.get("result") or {}
        return [
            {
                "label": "Required WAN",
                "value": f"{float(result.get('required_mbps', 0.0)):.1f} Mbps",
            },
            {
                "label": "Replica Storage",
                "value": f"{float(result.get('replica_storage_tb', 0.0)):.1f} TB",
            },
            {"label": "RPO Status", "value": "Pass" if result.get("meets_rpo") else "Risk"},
        ]
    return []


def _build_dashboard_site(design_payload: dict[str, Any], name: str) -> dict[str, Any]:
    repo = design_payload.get("repo") or {}
    roles = design_payload.get("roles") or {}
    proxies = roles.get("proxies") or {}
    backup_server = roles.get("backup_server") or {}
    network = design_payload.get("network") or {}
    risk = design_payload.get("risk") or {}
    repo_perf = design_payload.get("repo_perf") or {}
    cost = design_payload.get("cost") or {}
    sobr = design_payload.get("sobr") or {}

    transport_mode = str(proxies.get("transport_mode", "auto"))
    mb_per_core = {"direct_san": 20.0, "hotadd": 15.0, "nbd": 5.0}.get(transport_mode, 15.0)
    total_proxy_cores = int(proxies.get("total_proxy_cores", 0))

    return {
        "name": name,
        "total_repo_tb": float(repo.get("total_repo_tb", 0.0)),
        "primary_repo_tb": float(repo.get("primary_repo_tb", 0.0)),
        "gfs_repo_tb": float(repo.get("gfs_repo_tb", 0.0)),
        "capacity_tier_tb": float(sobr.get("capacity_tier_tb", 0.0)),
        "proxy_count": int(proxies.get("proxy_count", 0)),
        "total_proxy_cores": total_proxy_cores,
        "proxy_ram_gb": int(proxies.get("total_proxy_ram_gb", 0)),
        "transport_mode": transport_mode,
        "bs_cores": int(backup_server.get("cores", 0)),
        "bs_ram_gb": int(backup_server.get("ram_gb", 0)),
        "required_mb_s": float(repo_perf.get("required_mb_s", 0.0)),
        "proxy_capacity_mb_s": total_proxy_cores * mb_per_core,
        "proxy_load_ratio": float(repo_perf.get("required_mb_s", 0.0))
        / max(total_proxy_cores * mb_per_core, 1.0),
        "wan_required_mbps": float(network.get("required_mbps", 0.0)),
        "wan_meets_target": bool(network.get("meets_target", False)),
        "risk_level": str(risk.get("level", "unknown")),
        "risk_score": int(risk.get("total_score", 0)),
        "risk_details": risk.get("details", {}) or {},
        "yearly_onprem_usd": float(cost.get("yearly_onprem_usd", 0.0)),
        "monthly_object_usd": float(cost.get("monthly_object_usd", 0.0)),
        "cloud_comparison": cost.get("cloud_comparison", {}) or {},
        "three_year_tco": cost.get("three_year_tco", {}) or {},
        "break_even_years": float(cost.get("break_even_years", 0.0)),
        "orca": design_payload.get("orca"),
        "replication": design_payload.get("replication"),
        "nas": design_payload.get("nas"),
        "wan_accel": design_payload.get("wan_accel"),
        "license_estimate": design_payload.get("license_estimate"),
        "tape": design_payload.get("tape"),
        "veeam_one": design_payload.get("veeam_one"),
        "compliance": design_payload.get("compliance"),
        "notes": design_payload.get("notes") or {},
    }


def _flatten_mapping(value: Any, prefix: str = "") -> dict[str, Any]:
    items: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, nested in value.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            items.update(_flatten_mapping(nested, new_prefix))
        return items
    if isinstance(value, list):
        for index, nested in enumerate(value):
            new_prefix = f"{prefix}[{index}]"
            items.update(_flatten_mapping(nested, new_prefix))
        return items
    items[prefix] = value
    return items


def _csv_escape(value: str) -> str:
    if any(char in value for char in [",", '"', "\n"]):
        return '"' + value.replace('"', '""') + '"'
    return value


def _render_vm_blueprint(payload: dict[str, Any]) -> str:
    if payload.get("kind") == "multi-site":
        lines = [
            f"Multi-site repository footprint: {float(payload.get('total_repo_tb', 0.0)):.1f} TB",
            "",
        ]
        for site in payload.get("sites", []):
            design = site.get("design") or {}
            repo = design.get("repo") or {}
            roles = design.get("roles") or {}
            proxies = roles.get("proxies") or {}
            lines.append(f"{site.get('name', 'Site')}")
            lines.append(f"- Total repo: {float(repo.get('total_repo_tb', 0.0)):.1f} TB")
            lines.append(
                f"- Proxies: {int(proxies.get('proxy_count', 0))} "
                f"({int(proxies.get('total_proxy_cores', 0))} cores)"
            )
            lines.append(
                f"- Required WAN: {float((design.get('network') or {}).get('required_mbps', 0.0)):.1f} Mbps"
            )
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    repo = payload.get("repo") or {}
    roles = payload.get("roles") or {}
    proxies = roles.get("proxies") or {}
    backup_server = roles.get("backup_server") or {}
    network = payload.get("network") or {}
    return (
        "VM backup sizing\n"
        f"- Total repository: {float(repo.get('total_repo_tb', 0.0)):.1f} TB\n"
        f"- Proxies: {int(proxies.get('proxy_count', 0))} "
        f"({int(proxies.get('total_proxy_cores', 0))} cores / "
        f"{int(proxies.get('total_proxy_ram_gb', 0))} GB RAM)\n"
        f"- Backup server: {int(backup_server.get('cores', 0))} cores / "
        f"{int(backup_server.get('ram_gb', 0))} GB RAM\n"
        f"- Required WAN: {float(network.get('required_mbps', 0.0)):.1f} Mbps\n"
    )


def _render_page(
    request: Request,
    *,
    yaml_content: str,
    blueprint_output: str | None = None,
    cost_output: str | None = None,
    result_payload: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> HTMLResponse:
    dashboard = build_dashboard_from_payload(result_payload) if result_payload else None
    summary_cards = build_result_summary(result_payload) if result_payload else []
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "version": __version__,
            "yaml_content": yaml_content,
            "available_profiles": load_profile_names(),
            "blueprint_output": blueprint_output,
            "cost_output": cost_output,
            "result_payload": result_payload,
            "result_payload_json": json.dumps(result_payload, indent=2) if result_payload else None,
            "dashboard": dashboard,
            "summary_cards": summary_cards,
            "error_message": error_message,
        },
    )


@app.get("/", response_class=HTMLResponse)
async def root() -> RedirectResponse:
    """Redirect the base URL to the primary run page."""

    return RedirectResponse(url="/run")


@app.get("/run", response_class=HTMLResponse)
async def get_run(request: Request) -> HTMLResponse:
    """Render the main design page."""

    return _render_page(request, yaml_content=get_default_project_text())


@app.post("/run", response_class=HTMLResponse)
async def post_run(
    request: Request,
    yaml_content: str = Form(...),
    run_blueprint: Optional[str] = Form(None),
    run_cost: Optional[str] = Form(None),
) -> HTMLResponse:
    """Render a design run from submitted YAML text."""

    if len(yaml_content.encode("utf-8")) > MAX_PROJECT_TEXT_BYTES:
        return _render_page(
            request,
            yaml_content=yaml_content[:4096],
            error_message="Project input exceeds the 1 MB limit.",
        )

    if not (run_blueprint or run_cost):
        return _render_page(request, yaml_content=yaml_content)

    try:
        payload = design_payload_from_project_text(yaml_content, suffix=".yml")
    except Exception as exc:
        return _render_page(
            request,
            yaml_content=yaml_content,
            error_message=f"Unable to run the design: {exc}",
        )

    global LAST_RESULT_PAYLOAD, LAST_DASHBOARD_DATA
    LAST_RESULT_PAYLOAD = payload
    LAST_DASHBOARD_DATA = build_dashboard_from_payload(payload)

    return _render_page(
        request,
        yaml_content=yaml_content,
        blueprint_output=render_blueprint_human(payload) if run_blueprint else None,
        cost_output=render_cost_human(payload) if run_cost else None,
        result_payload=payload,
    )


@app.get("/export/csv")
async def export_csv() -> PlainTextResponse:
    """Export the most recent result payload as CSV."""

    if LAST_RESULT_PAYLOAD is None:
        raise HTTPException(status_code=400, detail="No design output is available yet.")

    return PlainTextResponse(
        content=build_csv_from_payload(LAST_RESULT_PAYLOAD),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=veeam-designer-results.csv"},
    )


@app.get("/export/report")
async def export_report(request: Request) -> PlainTextResponse:
    """Export a printable HTML report for VM-based dashboards."""

    if LAST_DASHBOARD_DATA is None or LAST_RESULT_PAYLOAD is None:
        raise HTTPException(
            status_code=400,
            detail="Printable reports are available after a VM or multi-site design run.",
        )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html_content = templates.TemplateResponse(
        request,
        "report.html",
        {
            "request": request,
            "version": __version__,
            "dashboard": LAST_DASHBOARD_DATA,
            "result_payload": LAST_RESULT_PAYLOAD,
            "generated_at": generated_at,
        },
    ).body.decode("utf-8")
    return PlainTextResponse(
        content=html_content,
        media_type="text/html",
        headers={"Content-Disposition": "attachment; filename=veeam-design-report.html"},
    )


@app.get("/api/health")
async def api_health() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok", "version": __version__}


@app.get("/api/profiles")
async def api_profiles() -> dict[str, list[str]]:
    """List available sizing profiles."""

    return {"profiles": load_profile_names()}


@app.post("/api/design")
async def api_design(yaml_content: str = Body(..., media_type="text/plain")) -> JSONResponse:
    """Accept YAML project definition text and return structured JSON output."""

    if len(yaml_content.encode("utf-8")) > MAX_PROJECT_TEXT_BYTES:
        raise HTTPException(status_code=413, detail="Project input exceeds the 1 MB limit.")

    try:
        payload = design_payload_from_project_text(yaml_content, suffix=".yml")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JSONResponse(content=payload)


def run(argv: list[str] | None = None) -> int:
    """Launch the web application with Uvicorn."""

    parser = argparse.ArgumentParser(description="Launch the Veeam Designer web interface.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Defaults to 127.0.0.1.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port. Defaults to 8000.")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development.")
    args = parser.parse_args(argv)

    uvicorn.run("ui.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
