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
        sites = payload.get("sites", [])
        data_movers = 0
        wan_targets_met = 0
        for site in sites:
            design = site.get("design", {}) or {}
            roles = design.get("roles", {}) or {}
            workers = roles.get("platform_workers") or {}
            proxies = roles.get("proxies") or {}
            data_movers += int(
                workers.get("worker_count", 0) if workers else proxies.get("proxy_count", 0)
            )
            if bool((design.get("network") or {}).get("meets_target", False)):
                wan_targets_met += 1

        return [
            {"label": "Sites", "value": str(len(sites))},
            {"label": "Repository", "value": f"{float(payload.get('total_repo_tb', 0.0)):.1f} TB"},
            {"label": "Data Movers", "value": str(data_movers)},
            {"label": "WAN Targets", "value": f"{wan_targets_met}/{len(sites)} met"},
            {
                "label": "Storage Planning/yr",
                "value": f"${sum(float((site.get('design', {}).get('cost', {}) or {}).get('total_yearly_usd', 0.0)) for site in sites):,.0f}",
            },
        ]

    if kind == "vm":
        repo = payload.get("repo") or {}
        roles = payload.get("roles") or {}
        cost = payload.get("cost") or {}
        network = payload.get("network") or {}
        risk = payload.get("risk") or {}
        proxies = roles.get("proxies") or {}
        platform_workers = roles.get("platform_workers") or {}
        backup_server = roles.get("backup_server") or {}
        mover_label = (
            f"{str(platform_workers.get('platform', '')).upper()} Workers"
            if platform_workers
            else "Proxies"
        )
        mover_count = (
            int(platform_workers.get("worker_count", 0))
            if platform_workers
            else int(proxies.get("proxy_count", 0))
        )
        wan_required = float(network.get("required_mbps", 0.0))
        wan_status = "Pass" if network.get("meets_target") else "Review"
        return [
            {"label": "Repository", "value": f"{float(repo.get('total_repo_tb', 0.0)):.1f} TB"},
            {"label": mover_label, "value": str(mover_count)},
            {
                "label": "Backup Server",
                "value": (
                    f"{int(backup_server.get('cores', 0))}c / "
                    f"{int(backup_server.get('ram_gb', 0))} GB"
                ),
            },
            {"label": "WAN / RPO", "value": f"{wan_required:.0f} Mbps · {wan_status}"},
            {"label": "Risk", "value": str(risk.get("level", "unknown")).upper()},
            {
                "label": "Storage Planning/yr",
                "value": f"${float(cost.get('total_yearly_usd', 0.0)):,.0f}",
            },
        ]

    if kind == "nas":
        result = payload.get("result") or {}
        cache_tb = float(result.get("cache_repo_tb", 0.0))
        cache_value = f"{cache_tb * 1024.0:.0f} GB" if 0 < cache_tb < 1 else f"{cache_tb:.1f} TB"
        return [
            {"label": "Repository", "value": f"{float(result.get('total_repo_tb', 0.0)):.1f} TB"},
            {"label": "File Proxies", "value": str(int(result.get("file_proxy_count", 0)))},
            {
                "label": "Proxy Compute",
                "value": (
                    f"{int(result.get('file_proxy_cores', 0))}c / "
                    f"{int(result.get('file_proxy_ram_gb', 0))} GB"
                ),
            },
            {"label": "Cache Repo", "value": cache_value},
        ]

    if kind == "physical":
        result = payload.get("result") or {}
        return [
            {"label": "Repository", "value": f"{float(result.get('total_repo_tb', 0.0)):.1f} TB"},
            {
                "label": "General Proxy",
                "value": (
                    f"{int(result.get('coordinator_cores', 0))}c / "
                    f"{int(result.get('coordinator_ram_gb', 0))} GB"
                ),
            },
            {
                "label": "Required Network",
                "value": f"{float(result.get('required_mbps', 0.0)):.1f} Mbps",
            },
        ]

    if kind == "replication":
        result = payload.get("result") or {}
        cards = [
            {
                "label": "Average WAN",
                "value": f"{float(result.get('required_mbps', 0.0)):.1f} Mbps",
            },
            {
                "label": "Replica Storage",
                "value": f"{float(result.get('replica_storage_tb', 0.0)):.1f} TB",
            },
            {
                "label": "Steady-State WAN",
                "value": "Sufficient" if result.get("meets_rpo") else "Insufficient",
            },
        ]
        if float(result.get("cdp_journal_tb", 0.0)) > 0:
            cards.append(
                {
                    "label": "CDP Retention",
                    "value": f"{float(result.get('cdp_journal_tb', 0.0)):.2f} TB",
                }
            )
        return cards

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
            f"- File proxies: {int(result.get('file_proxy_count', 0))} x "
            f"{int(result.get('file_proxy_cores_each', 0))} vCPU / "
            f"{int(result.get('file_proxy_ram_gb_each', 0))} GB RAM\n"
            f"- Cache-repository compute: {int(result.get('cache_repo_cores', 0))} vCPU / "
            f"{int(result.get('cache_repo_ram_gb', 0))} GB RAM\n"
        )

    if kind == "physical":
        result = payload.get("result") or {}
        return (
            "Physical / agent sizing\n"
            f"- Total repository: {float(result.get('total_repo_tb', 0.0)):.1f} TB\n"
            f"- Retained short-term data: {float(result.get('short_term_data_tb', 0.0)):.1f} TB\n"
            f"- Operational headroom: "
            f"{float(result.get('operational_headroom_tb', 0.0)):.1f} TB\n"
            f"- General-purpose proxy: {int(result.get('coordinator_cores', 0))} vCPU / "
            f"{int(result.get('coordinator_ram_gb', 0))} GB RAM\n"
            f"- Average required network: {float(result.get('required_mbps', 0.0)):.1f} Mbps\n"
        )

    if kind == "replication":
        result = payload.get("result") or {}
        lines = [
            "Replication sizing",
            f"- Average changed-data bandwidth: {float(result.get('required_mbps', 0.0)):.1f} Mbps",
            f"- Replica storage: {float(result.get('replica_storage_tb', 0.0)):.1f} TB",
            (
                "- WAN carries the average changed-data rate: "
                f"{'yes' if result.get('meets_rpo') else 'no'}"
            ),
        ]
        if int(result.get("cdp_proxy_count_per_side", 0)) > 0:
            lines.extend(
                [
                    (
                        f"- CDP proxies per side: {int(result.get('cdp_proxy_count_per_side', 0))} x "
                        f"{int(result.get('cdp_proxy_cores', 0))} vCPU / "
                        f"{int(result.get('cdp_proxy_ram_gb', 0))} GB RAM"
                    ),
                    f"- CDP short-term retention capacity: "
                    f"{float(result.get('cdp_journal_tb', 0.0)):.2f} TB",
                ]
            )
        return "\n".join(lines) + "\n"

    return "No design output available.\n"


def render_cost_human(payload: JSONDict) -> str:
    """Render configured planning-rate estimates without presenting them as live pricing."""

    kind = payload.get("kind")
    if kind == "multi-site":
        total_on_prem = 0.0
        total_object = 0.0
        lines = ["Cost planning assumptions"]
        for site in payload.get("sites", []):
            design = site.get("design") or {}
            cost = design.get("cost") or {}
            yearly_on_prem = float(cost.get("yearly_onprem_usd", 0.0))
            monthly_object = float(cost.get("monthly_object_usd", 0.0))
            total_on_prem += yearly_on_prem
            total_object += monthly_object * 12.0
            lines.append(
                f"- {site.get('name', 'Site')}: "
                f"configured on-prem ${yearly_on_prem:,.0f}/yr, "
                f"configured object ${monthly_object * 12.0:,.0f}/yr"
            )
        lines.append(f"- Total configured on-prem: ${total_on_prem:,.0f}/yr")
        lines.append(f"- Total configured object: ${total_object:,.0f}/yr")
        lines.append(
            "- These are configured planning rates, not Veeam quotes or live market pricing."
        )
        return "\n".join(lines) + "\n"

    if kind == "vm":
        cost = payload.get("cost") or {}
        return (
            "Cost planning assumptions\n"
            f"- Configured on-prem estimate: ${float(cost.get('yearly_onprem_usd', 0.0)):,.0f}/yr\n"
            f"- Configured object estimate: ${float(cost.get('yearly_object_usd', 0.0)):,.0f}/yr\n"
            f"- Total storage planning estimate: ${float(cost.get('total_yearly_usd', 0.0)):,.0f}/yr\n"
            "- Rates are explicit storage-planning inputs, not Veeam pricing or live market quotes. "
            "No provider comparison or break-even point is inferred.\n"
        )

    return "Cost projection is not generated for this calculator mode.\n"


def _build_dashboard_site(design_payload: JSONDict, name: str) -> JSONDict:
    repo = design_payload.get("repo") or {}
    roles = design_payload.get("roles") or {}
    proxies = roles.get("proxies") or {}
    platform_workers = roles.get("platform_workers") or {}
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
        "short_term_data_tb": float(repo.get("short_term_data_tb", 0.0)),
        "operational_headroom_tb": float(repo.get("operational_headroom_tb", 0.0)),
        "repo_calculation_basis": str(repo.get("calculation_basis", "")),
        "repo_notes": repo.get("notes", []) or [],
        "capacity_tier_tb": float(sobr.get("capacity_tier_tb", 0.0)),
        "proxy_count": int(proxies.get("proxy_count", 0)),
        "total_proxy_cores": total_proxy_cores,
        "proxy_deployment_mode": str(proxies.get("deployment_mode", "managed_os")),
        "proxy_allocated_cores": int(
            proxies.get("total_allocated_proxy_cores", 0) or total_proxy_cores
        ),
        "proxy_allocated_ram_gb": int(
            proxies.get("total_allocated_proxy_ram_gb", 0) or proxies.get("total_proxy_ram_gb", 0)
        ),
        "proxy_allocated_cores_each": int(
            proxies.get("allocated_cores_per_proxy", 0) or proxies.get("cores_per_proxy", 0)
        ),
        "proxy_allocated_ram_each": int(
            proxies.get("allocated_ram_gb_per_proxy", 0) or proxies.get("ram_gb_per_proxy", 0)
        ),
        "proxy_infra_system_disk_gb": int(proxies.get("infrastructure_system_disk_gb", 0)),
        "proxy_infra_data_disk_gb": int(proxies.get("infrastructure_data_disk_gb", 0)),
        "platform_worker_count": int(platform_workers.get("worker_count", 0)),
        "platform_worker_platform": str(platform_workers.get("platform", "")),
        "platform_worker_tasks": int(platform_workers.get("total_concurrent_tasks", 0)),
        "platform_worker_cores_each": int(platform_workers.get("cores_per_worker", 0)),
        "platform_worker_ram_each": int(platform_workers.get("ram_gb_per_worker", 0)),
        "platform_worker_disk_each": int(platform_workers.get("disk_gb_per_worker", 0)),
        "proxy_ram_gb": int(proxies.get("total_proxy_ram_gb", 0)),
        "transport_mode": transport_mode,
        "proxy_throughput_basis": str(proxies.get("throughput_basis", "auto")),
        "bs_cores": int(backup_server.get("cores", 0)),
        "bs_ram_gb": int(backup_server.get("ram_gb", 0)),
        "bs_deployment_mode": str(backup_server.get("deployment_mode", "")),
        "bs_system_disk_gb": int(backup_server.get("system_disk_gb", 0)),
        "bs_secondary_disk_gb": int(backup_server.get("secondary_disk_gb", 0)),
        "repo_host_count": int(hardened_repos.get("count", 0)) if hardened_repos else 0,
        "repo_host_tb": float(hardened_repos.get("tb_per_host", 0.0)) if hardened_repos else 0.0,
        "repo_host_cores": int(hardened_repos.get("cpu_cores_each", 0)) if hardened_repos else 0,
        "repo_host_ram_gb": int(hardened_repos.get("ram_gb_each", 0)) if hardened_repos else 0,
        "required_mb_s": float(repo_perf.get("required_mb_s", 0.0)),
        "proxy_capacity_mb_s": proxy_capacity_mb_s,
        "proxy_capacity_known": proxy_capacity_mb_s > 0,
        "proxy_load_ratio": (
            float(repo_perf.get("required_mb_s", 0.0)) / proxy_capacity_mb_s
            if proxy_capacity_mb_s > 0
            else 0.0
        ),
        "wan_required_mbps": float(network.get("required_mbps", 0.0)),
        "wan_meets_target": bool(network.get("meets_target", False)),
        "risk_level": str(risk.get("level", "unknown")),
        "risk_score": int(risk.get("total_score", 0)),
        "risk_details": risk.get("details", {}) or {},
        "yearly_onprem_usd": float(cost.get("yearly_onprem_usd", 0.0)),
        "yearly_object_usd": float(cost.get("yearly_object_usd", 0.0)),
        "monthly_object_usd": float(cost.get("monthly_object_usd", 0.0)),
        "total_yearly_usd": float(cost.get("total_yearly_usd", 0.0)),
        "cost_notes": cost.get("notes", []) or [],
        "capacity_tier_policy": str(sobr.get("capacity_tier_policy", "none")),
        "performance_tier_tb": float(sobr.get("performance_tier_tb", 0.0)),
        "moved_to_capacity_tb": float(sobr.get("moved_to_capacity_tb", 0.0)),
        "operational_restore_window_days": int(sobr.get("operational_restore_window_days", 0)),
        "move_eligible_short_term_tb": float(sobr.get("move_eligible_short_term_tb", 0.0)),
        "move_model_basis": str(sobr.get("move_model_basis", "")),
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
            workers = roles.get("platform_workers") or {}
            sobr = design.get("sobr") or {}
            lines.append(f"{site.get('name', 'Site')}")
            lines.append(f"- Total repo: {float(repo.get('total_repo_tb', 0.0)):.1f} TB")
            lines.append(f"- Retained data: {float(repo.get('short_term_data_tb', 0.0)):.1f} TB")
            lines.append(
                f"- Operational headroom: {float(repo.get('operational_headroom_tb', 0.0)):.1f} TB"
            )
            if workers:
                lines.append(
                    f"- {str(workers.get('platform', 'platform')).upper()} workers: "
                    f"{int(workers.get('worker_count', 0))} "
                    f"({int(workers.get('cores_per_worker', 0))} vCPU / "
                    f"{int(workers.get('ram_gb_per_worker', 0))} GB each)"
                )
            else:
                lines.append(
                    f"- Proxies: {int(proxies.get('proxy_count', 0))} "
                    f"({int(proxies.get('total_proxy_cores', 0))} cores)"
                )
            lines.append(
                f"- Required WAN: "
                f"{float((design.get('network') or {}).get('required_mbps', 0.0)):.1f} Mbps"
            )
            if str(sobr.get("capacity_tier_policy", "none")) != "none":
                lines.append(
                    f"- Capacity tier: {str(sobr.get('capacity_tier_policy', 'none')).replace('_', ' ')} / "
                    f"{float(sobr.get('performance_tier_tb', 0.0)):.1f} TB local / "
                    f"{float(sobr.get('capacity_tier_tb', 0.0)):.1f} TB object"
                )
                if str(sobr.get("capacity_tier_policy", "none")) in {"move", "copy_move"}:
                    lines.append(
                        f"- Operational restore window: "
                        f"{int(sobr.get('operational_restore_window_days', 0))} days"
                    )
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    repo = payload.get("repo") or {}
    roles = payload.get("roles") or {}
    proxies = roles.get("proxies") or {}
    workers = roles.get("platform_workers") or {}
    backup_server = roles.get("backup_server") or {}
    network = payload.get("network") or {}
    sobr = payload.get("sobr") or {}
    tier_policy = str(sobr.get("capacity_tier_policy", "none"))
    tier_lines = ""
    if tier_policy != "none":
        tier_lines = (
            f"- Capacity tier: {tier_policy.replace('_', ' ')} / "
            f"{float(sobr.get('performance_tier_tb', 0.0)):.1f} TB local / "
            f"{float(sobr.get('capacity_tier_tb', 0.0)):.1f} TB object\n"
        )
        if tier_policy in {"move", "copy_move"}:
            tier_lines += (
                f"- Operational restore window: "
                f"{int(sobr.get('operational_restore_window_days', 0))} days\n"
            )
        move_basis = str(sobr.get("move_model_basis", "")).strip()
        if move_basis:
            tier_lines += f"- Move basis: {move_basis}\n"

    mover_line = (
        f"- {str(workers.get('platform', 'platform')).upper()} workers: "
        f"{int(workers.get('worker_count', 0))} x "
        f"{int(workers.get('cores_per_worker', 0))} vCPU / "
        f"{int(workers.get('ram_gb_per_worker', 0))} GB RAM / "
        f"{int(workers.get('disk_gb_per_worker', 0))} GB disk "
        f"({int(workers.get('total_concurrent_tasks', 0))} concurrent tasks)\n"
        if workers
        else (
            f"- Proxies: {int(proxies.get('proxy_count', 0))} "
            f"({int(proxies.get('total_proxy_cores', 0))} cores / "
            f"{int(proxies.get('total_proxy_ram_gb', 0))} GB RAM)\n"
        )
    )
    basis = str(repo.get("calculation_basis", "")).strip()
    basis_line = f"- Repository basis: {basis}\n" if basis else ""
    return (
        "VM backup sizing\n"
        f"- Total repository: {float(repo.get('total_repo_tb', 0.0)):.1f} TB\n"
        f"- Retained short-term data: {float(repo.get('short_term_data_tb', 0.0)):.1f} TB\n"
        f"- Operational headroom: {float(repo.get('operational_headroom_tb', 0.0)):.1f} TB\n"
        f"{basis_line}"
        f"{tier_lines}"
        f"{mover_line}"
        f"- Backup server: {int(backup_server.get('cores', 0))} cores / "
        f"{int(backup_server.get('ram_gb', 0))} GB RAM "
        f"({backup_server.get('deployment_mode', 'unspecified')})\n"
        f"- Required WAN: {float(network.get('required_mbps', 0.0)):.1f} Mbps\n"
    )
