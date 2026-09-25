import json
from pathlib import Path
from typing import Any, List, Tuple

from .config import CONFIG, select_profile
from .models import (
    AgentInput,
    LicenseInput,
    NasInput,
    ReplicationInput,
    TapeInput,
    VeeamInput,
    VeeamOneInput,
    WanAccelInput,
)

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


def _vin_from_dict(d: dict) -> VeeamInput:
    return VeeamInput(
        total_data_tb=d["total_data_tb"],
        annual_growth_percent=d.get("annual_growth_percent", 0.0),
        daily_change_percent=d["daily_change_percent"],
        backup_type=d.get("backup_type", "synthetic_full_weekly"),
        primary_retention_days=d.get("primary_retention_days", 30),
        gfs_weekly_count=d.get("gfs_weekly_count", 4),
        gfs_monthly_count=d.get("gfs_monthly_count", 12),
        gfs_yearly_count=d.get("gfs_yearly_count", 3),
        backup_window_hours=d.get("backup_window_hours", 8.0),
        target_rpo_hours=d.get("target_rpo_hours", 24.0),
        compression_ratio=d.get("compression_ratio", CONFIG["compression_ratio_default"]),
        dedupe_ratio=d.get("dedupe_ratio", CONFIG["dedupe_ratio_default"]),
        throughput_mb_per_core=d.get("throughput_mb_per_core", 0.0),
        read_write_overhead=d.get("read_write_overhead", CONFIG["read_write_overhead"]),
        years_to_plan_for=d.get("years_to_plan_for", CONFIG["years_to_plan_for"]),
        vm_count=d.get("vm_count", 0),
        avg_vm_size_gb=d.get("avg_vm_size_gb", 0.0),
        wan_bandwidth_mbps=d.get("wan_bandwidth_mbps", 0.0),
        repo_type=d.get("repo_type", "sobr"),
        object_storage_provider=d.get("object_storage_provider", "generic"),
        objectfirst_node_tb=float(d.get("objectfirst_node_tb", 0.0)),
        hypervisor=d.get("hypervisor", "vmware"),
        has_san_access=d.get("has_san_access", False),
        on_host_proxy=d.get("on_host_proxy", True),
        # v5: platform and deployment inputs
        platform_host_count=int(d.get("platform_host_count", 0)),
        platform_cluster_count=int(d.get("platform_cluster_count", 1)),
        platform_concurrent_tasks=int(d.get("platform_concurrent_tasks", 0)),
        worker_task_limit=int(d.get("worker_task_limit", 4)),
        deployment_mode=d.get(
            "deployment_mode",
            "software_appliance" if d.get("v13_appliance", True) else "windows",
        ),
        proxy_deployment_mode=d.get("proxy_deployment_mode", "managed_os"),
        # Round 2
        workload_count=d.get("workload_count") or d.get("vm_count", 0),
        concurrent_jobs=d.get("concurrent_jobs", 5),
        indexing_enabled=d.get("indexing_enabled", False),
        v13_appliance=d.get("v13_appliance", True),
        # Round 3
        refs_xfs=d.get("refs_xfs", True),
        immutability_enabled=d.get("immutability_enabled", False),
        immutability_days=int(
            d.get(
                "immutability_days",
                d.get("primary_retention_days", 30)
                if d.get("immutability_enabled", False)
                else 0,
            )
        ),
        block_generation_days=d.get("block_generation_days", 10),
        # Round 5
        capacity_tier_enabled=d.get("capacity_tier_enabled", False),
        capacity_tier_fraction=d.get("capacity_tier_fraction", 0.0),
        direct_to_object=d.get("direct_to_object", False),
        capacity_tier_immutable=d.get("capacity_tier_immutable", False),
        # v3: compliance
        compliance_framework=d.get("compliance_framework", "none"),
        # v3: replication sub-input
        replication_input=_replication_input_from_dict(d),
        # v3: nas sub-input
        nas_input=_nas_input_from_site_dict(d),
        # Optional component sub-inputs
        wan_accel_input=_wan_accel_input_from_dict(d),
        tape_input=_tape_input_from_dict(d),
        license_input=_license_input_from_dict(d),
        veeam_one_input=_veeam_one_input_from_dict(d),
    )


def _nas_from_dict(d: dict) -> NasInput:
    return NasInput(
        source_tb=d["source_tb"],
        share_count=d.get("share_count", 70),
        file_count_millions=d.get("file_count_millions", 1.0),
        daily_change_pct=d.get("daily_change_pct", 5.0),
        backup_window_hours=d.get("backup_window_hours", 8.0),
        retention_days=d.get("retention_days", 14),
        gfs_weekly=d.get("gfs_weekly", 0),
        gfs_monthly=d.get("gfs_monthly", 0),
        gfs_yearly=d.get("gfs_yearly", 0),
        object_storage=d.get("object_storage", False),
        immutability_enabled=d.get("immutability_enabled", False),
        storage_native_cft=d.get("storage_native_cft", False),
        compress_pct=d.get("compress_pct", 30.0),
        growth_rate_pct=d.get("growth_rate_pct", 0.0),
        forecast_years=d.get("forecast_years", 0),
        concurrent_sources=int(d.get("concurrent_sources", 1)),
    )


def _agent_from_dict(d: dict) -> AgentInput:
    return AgentInput(
        machine_count=d["machine_count"],
        avg_size_gb=d["avg_size_gb"],
        daily_change_pct=d.get("daily_change_pct", 5.0),
        backup_window_hours=d.get("backup_window_hours", 8.0),
        retention_days=d.get("retention_days", 14),
        os_type=d.get("os_type", "windows"),
        network_bandwidth_mbps=d.get("network_bandwidth_mbps", 1000.0),
        concurrent_tasks=int(d.get("concurrent_tasks", 4)),
    )


def _replication_from_dict(d: dict) -> ReplicationInput:
    return ReplicationInput(
        source_tb=d["source_tb"],
        vm_count=d["vm_count"],
        wan_mbps=d["wan_mbps"],
        rpo_hours=d.get("rpo_hours", 1.0),
        cdp_enabled=d.get("cdp_enabled", False),
        rpo_seconds=d.get("rpo_seconds", 15),
        cdp_retention_hours=float(d.get("cdp_retention_hours", 24.0)),
        compression=d.get("compression", True),
        daily_change_pct=d.get("daily_change_pct", 5.0),
    )


def _replication_input_from_dict(d: dict):
    rep_d = d.get("replication")
    if not rep_d:
        return None
    from .models import ReplicationInput

    return ReplicationInput(
        source_tb=float(rep_d.get("source_tb", d.get("total_data_tb", 10.0))),
        vm_count=int(rep_d.get("vm_count", d.get("vm_count", 0))),
        wan_mbps=float(rep_d.get("wan_mbps", d.get("wan_bandwidth_mbps", 100.0))),
        rpo_hours=float(rep_d.get("rpo_hours", 1.0)),
        cdp_enabled=bool(rep_d.get("cdp_enabled", False)),
        rpo_seconds=int(rep_d.get("rpo_seconds", 15)),
        cdp_retention_hours=float(rep_d.get("cdp_retention_hours", 24.0)),
        compression=bool(rep_d.get("compression", True)),
        daily_change_pct=float(rep_d.get("daily_change_pct", 5.0)),
    )


def _nas_input_from_site_dict(d: dict):
    nas_d = d.get("nas")
    if not nas_d:
        return None
    return _nas_from_dict(nas_d)


def _wan_accel_input_from_dict(d: dict):
    wan_d = d.get("wan_accel")
    if not wan_d:
        return None
    return WanAccelInput(
        source_tb=float(wan_d.get("source_tb", d.get("total_data_tb", 0.0))),
        wan_mbps=float(wan_d.get("wan_mbps", d.get("wan_bandwidth_mbps", 0.0))),
        backup_copy_frequency_hours=float(wan_d.get("backup_copy_frequency_hours", 24.0)),
        dedupe_ratio=float(wan_d.get("dedupe_ratio", 1.0)),
        compression_ratio=float(wan_d.get("compression_ratio", 1.0)),
        daily_change_pct=float(wan_d.get("daily_change_pct", d.get("daily_change_percent", 5.0))),
        mode=str(wan_d.get("mode", "auto")),
        os_type_count=int(wan_d.get("os_type_count", 0)),
        cache_size_gb_per_source=int(wan_d.get("cache_size_gb_per_source", 100)),
    )


def _tape_input_from_dict(d: dict):
    tape_d = d.get("tape")
    if not tape_d:
        return None
    return TapeInput(
        archive_tb=float(tape_d.get("archive_tb", 0.0)),
        lto_generation=int(tape_d.get("lto_generation", 9)),
        retention_years=int(tape_d.get("retention_years", 7)),
        daily_change_pct=float(tape_d.get("daily_change_pct", 1.0)),
        media_compression_ratio=float(tape_d.get("media_compression_ratio", 1.0)),
        cost_per_cartridge_usd=float(tape_d.get("cost_per_cartridge_usd", 0.0)),
    )


def _license_input_from_dict(d: dict):
    lic_d = d.get("license")
    if not lic_d:
        return None
    return LicenseInput(
        vm_count=int(lic_d.get("vm_count", d.get("vm_count", 0))),
        physical_count=int(lic_d.get("physical_count", 0)),
        nas_tb=float(lic_d.get("nas_tb", 0.0)),
        cloud_workloads=int(lic_d.get("cloud_workloads", 0)),
        license_type=str(lic_d.get("license_type", "instance")),
        occupied_sockets=int(lic_d.get("occupied_sockets", 0)),
    )


def _veeam_one_input_from_dict(d: dict):
    one_d = d.get("veeam_one")
    if not one_d:
        return None
    return VeeamOneInput(
        protected_vms=int(one_d.get("protected_vms", d.get("vm_count", 0))),
        protected_physical=int(one_d.get("protected_physical", 0)),
        retention_days=int(one_d.get("retention_days", 30)),
        enterprise_manager=bool(one_d.get("enterprise_manager", False)),
        vspc_tenants=int(one_d.get("vspc_tenants", 0)),
        connected_vbr_servers=int(one_d.get("connected_vbr_servers", 1)),
    )


def _dispatch_workload(wtype: str, d: dict):
    """Return the appropriate input object based on workload_type."""
    wtype = (wtype or "vm").lower()
    if wtype == "nas":
        return _nas_from_dict(d)
    if wtype in ("physical", "agent"):
        return _agent_from_dict(d)
    if wtype == "replication":
        return _replication_from_dict(d)
    return _vin_from_dict(d)


def _load_serialized_data(text: str, *, suffix: str) -> dict[str, Any]:
    if suffix.lower() in {".yml", ".yaml"} and yaml is not None:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    if not isinstance(data, dict):
        raise ValueError("Project definition must be a top-level JSON or YAML object.")
    return data


def _project_from_data(data: dict[str, Any]):
    """Build the appropriate workload input object(s) from a parsed payload."""

    profile = data.get("profile")
    select_profile(profile if isinstance(profile, str) else None)

    workload_type = data.get("workload_type", "vm")

    if "sites" in data:
        sites_def = data["sites"]
        sites: List[Tuple[str, VeeamInput]] = []
        top_compliance = data.get("compliance_framework", "none")
        for s in sites_def:
            name = s.get("name", "site")
            vin_kwargs = s.get("veeam_input") or s
            # Inject top-level compliance_framework into site if not already set
            if "compliance_framework" not in vin_kwargs and top_compliance != "none":
                vin_kwargs = dict(vin_kwargs)
                vin_kwargs["compliance_framework"] = top_compliance
            # Sites always use VM workload path (multi-site is VM-only for now)
            vin = _vin_from_dict(vin_kwargs)
            sites.append((name, vin))
        return sites
    vin_kwargs = data.get("veeam_input") or data
    return _dispatch_workload(workload_type, vin_kwargs)


def load_project_text(text: str, *, suffix: str = ".yml"):
    """Load a YAML or JSON project definition from text."""

    data = _load_serialized_data(text, suffix=suffix)
    return _project_from_data(data)


def load_project(path: Path):
    """Load a YAML or JSON project file from disk."""

    text = path.read_text(encoding="utf-8")
    return load_project_text(text, suffix=path.suffix)
