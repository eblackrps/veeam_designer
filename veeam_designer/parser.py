import json
from pathlib import Path
from typing import List, Tuple

from .models import VeeamInput, NasInput, AgentInput, ReplicationInput
from .config import CONFIG, select_profile

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
        throughput_mb_per_core=d.get("throughput_mb_per_core", CONFIG["throughput_mb_per_core"]),
        vm_count=d.get("vm_count", 0),
        avg_vm_size_gb=d.get("avg_vm_size_gb", 0.0),
        wan_bandwidth_mbps=d.get("wan_bandwidth_mbps", 0.0),
        repo_type=d.get("repo_type", "sobr"),
        hypervisor=d.get("hypervisor", "vmware"),
        has_san_access=d.get("has_san_access", False),
        on_host_proxy=d.get("on_host_proxy", True),
        # Round 2
        workload_count=d.get("workload_count") or d.get("vm_count", 0),
        concurrent_jobs=d.get("concurrent_jobs", 5),
        indexing_enabled=d.get("indexing_enabled", False),
        v13_appliance=d.get("v13_appliance", True),
        # Round 3
        refs_xfs=d.get("refs_xfs", True),
        immutability_enabled=d.get("immutability_enabled", False),
        block_generation_days=d.get("block_generation_days", 10),
        # Round 5
        capacity_tier_enabled=d.get("capacity_tier_enabled", False),
        capacity_tier_fraction=d.get("capacity_tier_fraction", 0.5),
        direct_to_object=d.get("direct_to_object", False),
        capacity_tier_immutable=d.get("capacity_tier_immutable", False),
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
    )


def _replication_from_dict(d: dict) -> ReplicationInput:
    return ReplicationInput(
        source_tb=d["source_tb"],
        vm_count=d["vm_count"],
        wan_mbps=d["wan_mbps"],
        rpo_hours=d.get("rpo_hours", 1.0),
        cdp_enabled=d.get("cdp_enabled", False),
        rpo_seconds=d.get("rpo_seconds", 15),
        compression=d.get("compression", True),
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


def load_project(path: Path):
    """Load a YAML/JSON project file and return the appropriate input object(s)."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yml", ".yaml"} and yaml is not None:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    profile = data.get("profile")
    if profile:
        select_profile(profile)

    workload_type = data.get("workload_type", "vm")

    if "sites" in data:
        sites_def = data["sites"]
        sites: List[Tuple[str, VeeamInput]] = []
        for s in sites_def:
            name = s.get("name", "site")
            vin_kwargs = s.get("veeam_input") or s
            # Sites always use VM workload path (multi-site is VM-only for now)
            vin = _vin_from_dict(vin_kwargs)
            sites.append((name, vin))
        return sites
    else:
        vin_kwargs = data.get("veeam_input") or data
        return _dispatch_workload(workload_type, vin_kwargs)
