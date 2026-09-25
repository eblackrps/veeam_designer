"""Physical / Veeam Agent workload sizing."""

from __future__ import annotations

from .config import CONFIG
from .models import AgentDesign, AgentInput


def size_agent(ain: AgentInput) -> AgentDesign:
    """Size Agent backup capacity and general-purpose proxy minimum resources."""

    total_data_tb = max(0, ain.machine_count) * max(0.0, ain.avg_size_gb) / 1024.0
    daily_change_tb = total_data_tb * max(0.0, ain.daily_change_pct) / 100.0

    # Managed Agent daily retention in VBR 13 keeps N+1 days and never fewer than 3 points.
    restore_points = max(3, max(0, int(ain.retention_days)) + 1)
    short_term_data_tb = total_data_tb + daily_change_tb * (restore_points - 1)

    # Use the same documented disk-repository transformation reserve as the VM engine.
    # This is headroom, not retained backup data.
    transformation_factor = max(0.0, float(CONFIG.get("repo_overhead_factor", 1.25)))
    operational_headroom_tb = total_data_tb * transformation_factor
    total_repo_tb = short_term_data_tb + operational_headroom_tb

    if ain.backup_window_hours <= 0:
        raise ValueError("backup_window_hours must be greater than zero")

    required_mb_s = (daily_change_tb * 1024.0 * 1024.0) / (
        ain.backup_window_hours * 3600.0
    )
    required_mbps = required_mb_s * 8.0
    available_mbps = max(0.0, ain.network_bandwidth_mbps)

    tasks = max(1, int(ain.concurrent_tasks))
    # Current general-purpose proxy minimum for Agent integration:
    # 2 vCPU minimum, with 2 vCPU required per concurrent task; 2 GB RAM + 1 GB/task.
    proxy_cores = max(2, 2 * tasks)
    proxy_ram_gb = 2 + tasks

    notes: list[str] = [
        f"Agent repository capacity assumes one successful restore point per day and uses "
        f"{restore_points} retained restore points (VBR 13 N+1 retention, minimum 3): "
        "one full plus changed data for the remaining points.",
        "No backup-data compression or deduplication ratio is invented for Agent workloads.",
        f"Operational headroom adds one full backup x {transformation_factor:.2f}, matching "
        "Veeam Best Practice's documented minimum for backup-chain transformation. "
        "One-off full-backup headroom is a separate planning consideration because Veeam does "
        "not publish a single universal quantity for it.",
        f"General-purpose proxy minimum for {tasks} concurrent Agent task(s): "
        f"{proxy_cores} vCPU / {proxy_ram_gb} GB RAM. The legacy output field name "
        "'coordinator' is retained for API compatibility but represents proxy resources.",
    ]

    if available_mbps <= 0:
        notes.append("No network bandwidth was supplied; backup-window feasibility was not validated.")
    elif required_mbps > available_mbps:
        notes.append(
            f"Average changed data requires {required_mbps:.1f} Mbps inside the backup window, "
            f"above the configured {available_mbps:.1f} Mbps."
        )

    return AgentDesign(
        total_repo_tb=round(total_repo_tb, 1),
        coordinator_cores=proxy_cores,
        coordinator_ram_gb=proxy_ram_gb,
        short_term_data_tb=round(short_term_data_tb, 1),
        operational_headroom_tb=round(operational_headroom_tb, 1),
        required_mbps=round(required_mbps, 1),
        notes=notes,
    )
