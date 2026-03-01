import json
from pathlib import Path
from typing import List, Tuple

from .models import VeeamInput
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
    )


def load_project(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yml", ".yaml"} and yaml is not None:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    profile = data.get("profile")
    if profile:
        select_profile(profile)

    if "sites" in data:
        sites_def = data["sites"]
        sites: List[Tuple[str, VeeamInput]] = []
        for s in sites_def:
            name = s.get("name", "site")
            vin_kwargs = s.get("veeam_input") or s
            vin = _vin_from_dict(vin_kwargs)
            sites.append((name, vin))
        return sites
    else:
        vin_kwargs = data.get("veeam_input") or data
        return _vin_from_dict(vin_kwargs)
