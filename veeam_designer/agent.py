"""
Agent / Physical machine backup sizing module.

Mirrors the Veeam Calculator – Agent Backup tab behaviour:
  - Network-based transfer (NBD-equivalent: 5 MB/s per core)
  - Agent coordinator VM sized by machine count
  - Repository sizing reuses the VM engine formulas
"""

from __future__ import annotations

from math import ceil

from .config import CONFIG
from .models import AgentDesign, AgentInput


_AGENT_MB_PER_CORE = 5.0  # network throughput per core (no SAN/HotAdd for agents)


def size_agent(ain: AgentInput) -> AgentDesign:
    """Return an AgentDesign for the given AgentInput."""
    total_data_tb = ain.machine_count * ain.avg_size_gb / 1024.0
    daily_change_tb = total_data_tb * ain.daily_change_pct / 100.0

    # Repository sizing (same logic as VM engine)
    weeks_in_retention = ain.retention_days / 7.0
    week_full_tb = total_data_tb
    week_incr_tb = daily_change_tb * 6
    primary_logical_tb = (week_full_tb + week_incr_tb) * weeks_in_retention
    # Agents default to ~1.3 compression (lower than VM due to OS overhead)
    compression_ratio = 1.3
    primary_repo_tb = (primary_logical_tb / compression_ratio) * CONFIG["repo_overhead_factor"]
    total_repo_tb = primary_repo_tb

    # Throughput and coordinator sizing
    if ain.backup_window_hours > 0:
        required_mb_s = (daily_change_tb * 1024.0 * 1024.0) / (ain.backup_window_hours * 3600.0)
    else:
        required_mb_s = 0.0

    # Validate against available network bandwidth
    available_mb_s = ain.network_bandwidth_mbps / 8.0
    # bottleneck unused; kept for future use

    # Agent coordinator: 1 coordinator per 100 machines minimum
    coordinator_cores = max(2, ceil(ain.machine_count / 100))
    coordinator_ram_gb = max(8, coordinator_cores * 2)

    notes: list[str] = []
    if required_mb_s > available_mb_s > 0:
        deficit = required_mb_s - available_mb_s
        notes.append(
            f"Network bandwidth ({ain.network_bandwidth_mbps:.0f} Mbps) is insufficient "
            f"for {required_mb_s * 8:.0f} Mbps of backup traffic within the window. "
            f"Deficit: {deficit * 8:.0f} Mbps. Extend backup window or increase bandwidth."
        )
    if ain.os_type.lower() == "linux":
        notes.append(
            "Linux agents: ensure Veeam Agent for Linux is deployed and CBT driver is loaded "
            "for efficient incremental tracking."
        )
    elif ain.os_type.lower() == "windows":
        notes.append(
            "Windows agents: Volume Shadow Copy (VSS) is used for consistent snapshots. "
            "Ensure VSS writers are healthy on all protected machines."
        )
    if ain.machine_count > 200:
        notes.append(
            f"Large agent deployment ({ain.machine_count} machines): consider a dedicated "
            "distribution server to reduce coordinator load."
        )

    return AgentDesign(
        total_repo_tb=round(total_repo_tb, 1),
        coordinator_cores=coordinator_cores,
        coordinator_ram_gb=coordinator_ram_gb,
        notes=notes,
    )
