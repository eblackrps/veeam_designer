from typing import List

from .models import NetworkPlan, RepoSizing, VeeamInput
from .workload_math import projected_daily_change_tb, tb_to_mb


def build_network_plan(vin: VeeamInput, repo: RepoSizing) -> NetworkPlan:
    """Validate whether configured WAN can carry average changed data inside the transfer window."""

    del repo  # reserved for future repository-aware copy calculations
    notes: List[str] = []
    daily_change_size_tb = projected_daily_change_tb(
        total_data_tb=vin.total_data_tb,
        daily_change_percent=vin.daily_change_percent,
        annual_growth_percent=vin.annual_growth_percent,
        years_to_plan_for=vin.years_to_plan_for,
    )
    daily_copy_mb = tb_to_mb(daily_change_size_tb)
    copy_window_sec = max(vin.backup_window_hours, 0.01) * 3600.0
    required_mbps = (daily_copy_mb / copy_window_sec) * 8.0

    if vin.wan_bandwidth_mbps > 0:
        meets = required_mbps <= vin.wan_bandwidth_mbps
        if meets:
            notes.append(
                f"WAN can carry the average projected daily change inside the configured "
                f"{vin.backup_window_hours:g}-hour transfer window "
                f"({required_mbps:.1f} Mbps required)."
            )
        else:
            notes.append(
                f"WAN cannot carry the average projected daily change inside the configured "
                f"{vin.backup_window_hours:g}-hour transfer window: {required_mbps:.1f} Mbps "
                f"required vs {vin.wan_bandwidth_mbps:.1f} Mbps available."
            )
    else:
        meets = True
        notes.append("No WAN bandwidth specified; transfer-window feasibility was not validated.")

    notes.append(
        "An achievable RPO is not derived from bandwidth alone. Job scheduling, source restore-point "
        "availability, latency, bursts, and backlog all affect actual RPO."
    )

    return NetworkPlan(
        required_mbps=round(required_mbps, 1),
        achievable_rpo_hours=0.0,
        meets_target=meets,
        notes=notes,
    )
