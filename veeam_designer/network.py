from typing import List
from .models import NetworkPlan, VeeamInput, RepoSizing


def build_network_plan(vin: VeeamInput, repo: RepoSizing) -> NetworkPlan:
    notes: List[str] = []
    daily_change_tb = vin.total_data_tb * vin.daily_change_percent / 100
    daily_copy_mb = daily_change_tb * 1024 * 1024
    copy_window_sec = vin.backup_window_hours * 3600 or 1

    required_mb_s = daily_copy_mb / copy_window_sec
    required_mbps = required_mb_s * 8
    achievable_rpo = vin.target_rpo_hours
    meets = True

    if vin.wan_bandwidth_mbps > 0:
        if required_mbps > vin.wan_bandwidth_mbps:
            factor = required_mbps / max(vin.wan_bandwidth_mbps, 1)
            achievable_rpo = vin.target_rpo_hours * factor
            meets = False
            notes.append(
                f"WAN is undersized: requires ~{required_mbps:.1f} Mbps, "
                f"available {vin.wan_bandwidth_mbps:.1f} Mbps. RPO will drift."
            )
        else:
            notes.append(
                f"WAN bandwidth appears sufficient for daily change (~{required_mbps:.1f} Mbps required)."
            )
    else:
        notes.append("No WAN bandwidth specified: cannot validate copy/replication RPO.")

    return NetworkPlan(
        required_mbps=round(required_mbps, 1),
        achievable_rpo_hours=round(achievable_rpo, 1),
        meets_target=meets,
        notes=notes,
    )
