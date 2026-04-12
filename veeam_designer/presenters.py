"""Presentation helpers shared by the web UI, Pages app, and exports."""

from __future__ import annotations

from typing import Any

JSONDict = dict[str, Any]


def build_csv_from_payload(payload: JSONDict) -> str:
    """Flatten a result payload into a generic key/value CSV export."""

    rows = ["field,value"]
    for field, value in _flatten_mapping(payload).items():
        rows.append(f"{_csv_escape(field)},{_csv_escape(str(value))}")
    return "\n".join(rows) + "\n"


def build_dashboard_from_payload(payload: JSONDict | None) -> JSONDict | None:
    """Build a dashboard summary for VM-oriented outputs."""

    if payload is None:
        return None

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


def build_result_summary(payload: JSONDict | None) -> list[dict[str, str]]:
    """Build headline metrics for the dashboard summary strip."""

    if payload is None:
        return []

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


def render_blueprint_human(payload: JSONDict) -> str:
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


def render_cost_human(payload: JSONDict) -> str:
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


def _build_dashboard_site(design_payload: JSONDict, name: str) -> JSONDict:
    repo = design_payload.get("repo") or {}
    roles = design_payload.get("roles") or {}
    proxies = roles.get("proxies") or {}
    backup_server = roles.get("backup_server") or {}
    hardened_repos = roles.get("hardened_repos") or {}
    network = design_payload.get("network") or {}
    risk = design_payload.get("risk") or {}
    repo_perf = design_payload.get("repo_perf") or {}
    cost = design_payload.get("cost") or {}
    sobr = design_payload.get("sobr") or {}

    transport_mode = str(proxies.get("transport_mode", "auto"))
    total_proxy_cores = int(proxies.get("total_proxy_cores", 0))
    proxy_capacity_mb_s = float(proxies.get("estimated_capacity_mb_s", 0.0))

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
        "proxy_throughput_basis": str(proxies.get("throughput_basis", "auto")),
        "bs_cores": int(backup_server.get("cores", 0)),
        "bs_ram_gb": int(backup_server.get("ram_gb", 0)),
        "repo_host_count": int(hardened_repos.get("count", 0)) if hardened_repos else 0,
        "repo_host_tb": float(hardened_repos.get("tb_per_host", 0.0)) if hardened_repos else 0.0,
        "repo_host_cores": int(hardened_repos.get("cpu_cores_each", 0)) if hardened_repos else 0,
        "repo_host_ram_gb": int(hardened_repos.get("ram_gb_each", 0)) if hardened_repos else 0,
        "required_mb_s": float(repo_perf.get("required_mb_s", 0.0)),
        "proxy_capacity_mb_s": proxy_capacity_mb_s,
        "proxy_load_ratio": float(repo_perf.get("required_mb_s", 0.0))
        / max(proxy_capacity_mb_s, 1.0),
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


def _flatten_mapping(value: Any, prefix: str = "") -> JSONDict:
    items: JSONDict = {}
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


def _render_vm_blueprint(payload: JSONDict) -> str:
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
