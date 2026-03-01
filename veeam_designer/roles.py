from __future__ import annotations

import math
from .models import (
    VeeamInput,
    RepoSizing,
    ProxySizing,
    BackupServerSizing,
    HardenedRepoHost,
    GatewayServerSizing,
    RolePlan,
)
from .config import CONFIG


def size_proxies(vin: VeeamInput) -> ProxySizing:
    """
    Size proxy concurrency based on daily change rate and backup window.
    """
    daily_change_tb = vin.total_data_tb * vin.daily_change_percent / 100
    daily_backup_mb = daily_change_tb * 1024 * 1024

    backup_window_sec = vin.backup_window_hours * 3600
    if backup_window_sec <= 0:
        raise ValueError("backup_window_hours must be > 0")

    required_throughput_mb_s = daily_backup_mb / backup_window_sec

    cores_needed = (required_throughput_mb_s / vin.throughput_mb_per_core) * vin.read_write_overhead

    cores_per_proxy = 4
    proxy_count = max(1, math.ceil(cores_needed / cores_per_proxy))

    tasks_per_core = CONFIG["tasks_per_core"]
    total_proxy_cores = proxy_count * cores_per_proxy
    total_parallel_tasks = total_proxy_cores * tasks_per_core

    return ProxySizing(
        proxy_count=proxy_count,
        cores_per_proxy=cores_per_proxy,
        total_proxy_cores=total_proxy_cores,
        total_parallel_tasks=total_parallel_tasks,
        required_throughput_mb_s=round(required_throughput_mb_s, 1),
    )


def size_backup_server(proxies: ProxySizing, vin: VeeamInput) -> BackupServerSizing:
    """
    Size backup server relative to proxy core count.
    """
    baseline_cores = max(4, math.ceil(proxies.total_proxy_cores * 0.5))
    ram_gb = max(16, baseline_cores * 2)
    return BackupServerSizing(cores=baseline_cores, ram_gb=ram_gb)


def size_hardened_repo(repo: RepoSizing) -> HardenedRepoHost:
    """
    Size hardened repository hosts.

    Logic:
      - Cap per-host repo usage at ~1 PB (configurable)
      - Recommend 250 TB volumes (configurable)
      - Count hosts needed to stay under cap
    """
    host_cap_tb = float(CONFIG.get("hardened_tb_per_host_cap", 1000.0))      # default: 1 PB
    volume_target_tb = float(CONFIG.get("hardened_volume_tb_target", 250.0))  # default: 250 TB per volume

    host_count = max(1, math.ceil(repo.total_repo_tb / host_cap_tb))
    tb_per_host = repo.total_repo_tb / host_count

    notes = (
        f"Hardened repo host capped at ~{host_cap_tb:.0f} TB per host. "
        f"Recommended volume/extent size ~{volume_target_tb:.0f} TB. "
        "Use XFS/ReFS with immutability, separate mgmt/data NICs, "
        "and avoid domain-joining hardened hosts."
    )

    return HardenedRepoHost(
        count=host_count,
        tb_per_host=round(tb_per_host, 1),
        notes=notes,
    )


def size_gateways(repo: RepoSizing) -> GatewayServerSizing:
    """
    Size object storage gateway servers.
    Only used when repo_type = object.
    """
    total_tb = repo.total_repo_tb
    count = 1 if total_tb <= 200 else 2

    cores_each = 4
    ram_gb_each = 16
    notes = (
        "Object storage gateway servers for S3-compatible capacity tier. "
        "Stateless data movers. Required only for object repositories."
    )

    return GatewayServerSizing(
        count=count,
        cores_each=cores_each,
        ram_gb_each=ram_gb_each,
        notes=notes,
    )


def build_role_plan(vin: VeeamInput, repo: RepoSizing) -> RolePlan:
    """
    Build full Veeam role plan:
      - Backup server
      - Proxies
      - Hardened repositories
      - Gateways ONLY for object storage
    """
    proxies = size_proxies(vin)
    backup_server = size_backup_server(proxies, vin)
    hardened = size_hardened_repo(repo)

    # Gateways ONLY for repo_type == object
    gateways = size_gateways(repo) if vin.repo_type == "object" else None

    return RolePlan(
        backup_server=backup_server,
        proxies=proxies,
        hardened_repos=hardened,
        gateways=gateways,
    )
