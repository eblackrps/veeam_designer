from __future__ import annotations

import argparse
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
from veeam_designer.presenters import (
    build_csv_from_payload,
    build_dashboard_from_payload,
    build_result_summary,
    render_blueprint_human,
    render_cost_human,
)
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


def _server_result_bundle(
    payload: dict[str, Any] | None,
    *,
    blueprint_output: str | None,
    cost_output: str | None,
) -> dict[str, Any] | None:
    if payload is None:
        return None

    return {
        "payload": payload,
        "summary_cards": build_result_summary(payload),
        "dashboard": build_dashboard_from_payload(payload),
        "blueprint": blueprint_output or render_blueprint_human(payload),
        "cost": cost_output or render_cost_human(payload),
    }


def _render_page(
    request: Request,
    *,
    yaml_content: str,
    blueprint_output: str | None = None,
    cost_output: str | None = None,
    result_payload: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "version": __version__,
            "runtime": "server",
            "yaml_content": yaml_content,
            "available_profiles": load_profile_names(),
            "form_action": "/run",
            "form_method": "post",
            "hero_pill": "Interactive sizing studio",
            "hero_meta_lines": [
                f"Version {__version__}",
                "REST API available at /api/design",
                "Docker-ready via uvicorn ui.main:app",
            ],
            "static_css_href": str(request.url_for("static", path="app.css")),
            "app_js_href": str(request.url_for("static", path="app.js")),
            "pyodide_script_src": None,
            "yaml_library_src": None,
            "bootstrap_payload": {
                "runtime": "server",
                "version": __version__,
                "yamlContent": yaml_content,
                "formAction": "/run",
                "resultBundle": _server_result_bundle(
                    result_payload,
                    blueprint_output=blueprint_output,
                    cost_output=cost_output,
                ),
                "errorMessage": error_message,
            },
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
    rendered_response = templates.TemplateResponse(
        request,
        "report.html",
        {
            "request": request,
            "version": __version__,
            "dashboard": LAST_DASHBOARD_DATA,
            "result_payload": LAST_RESULT_PAYLOAD,
            "generated_at": generated_at,
        },
    )
    rendered_body = rendered_response.body
    if isinstance(rendered_body, memoryview):
        rendered_body = rendered_body.tobytes()
    html_content = rendered_body.decode("utf-8")
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
