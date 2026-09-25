"""Physical / Veeam Agent workload sizing."""

from __future__ import annotations

from .config import CONFIG
from .models import AgentDesign, AgentInput


def size_agent(ain: AgentInput) -> AgentDesign:
    """Size Agent repository capacity and general-purpose proxy minimum resources."""

    total_data_tb = max(0, ain.machine_count) * max(0.0, ain.avg_size_gb) / 1024.0
    daily_change_tb = total_data_tb * max(0.0, ain.daily_change_pct) / 100.0

    # Managed Agent daily retention in VBR v13 keeps N+1 days and never fewer than 3 points.
    restore_points = max(3, max(0, ain.retention_days) + 1)
    chain_tb = total_data_tb + daily_change_tb * (restore_points - 1)
    reserve_factor = max(1.0, float(CONFIG.get("repo_overhead_factor", 1.0)))
    total_repo_tb = chain_tb * reserve_factor

    if ain.backup_window_hours > 0:
        required_mb_s = (daily_change_tb * 1024.0 * 1024.0) / (
            ain.backup_window_hours * 3600.0
        )
    else:
        required_mb_s = 0.0
    available_mb_s = max(0.0, ain.network_bandwidth_mbps) / 8.0

    tasks = max(1, ain.concurrent_tasks)
    # Current general-purpose proxy system requirements for Agent integration:
    # 2 vCPU minimum and 2 vCPU required per concurrent task; Veeam recommends
    # additional CPU headroom for higher throughput.
    proxy_cores = max(2, 2 * tasks)
    proxy_ram_gb = 2 + tasks

    notes: list[str] = [
        f"Repository capacity uses {restore_points} retained restore points "
        f"(v13 N+1 daily retention, minimum 3): one full plus changed data for the remaining points.",
        "No backup-data compression ratio is invented for physical workloads. Capacity is based on "
        "source and changed data before storage-side reduction.",
        f"Provisioned capacity includes the configured {(reserve_factor - 1.0) * 100:.0f}% "
        "operational reserve." if reserve_factor > 1.0 else "No additional repository reserve is configured.",
        f"General-purpose proxy minimum for {tasks} concurrent Agent task(s): "
        f"{proxy_cores} vCPU / {proxy_ram_gb} GB RAM. Veeam recommends additional CPU for "
        "higher-throughput concurrent processing.",
    ]

    if required_mb_s > available_mb_s > 0:
        notes.append(
            f"Configured network provides {ain.network_bandwidth_mbps:.0f} Mbps but average changed "
            f"data requires {required_mb_s * 8:.0f} Mbps within the backup window."
        )
    elif ain.network_bandwidth_mbps <= 0:
        notes.append("No network bandwidth was supplied; backup-window feasibility was not validated.")

    return AgentDesign(
        total_repo_tb=round(total_repo_tb, 1),
        coordinator_cores=proxy_cores,
        coordinator_ram_gb=proxy_ram_gb,
        notes=notes,
    )
