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

# ---------------------------------------------------------------------------
# Round 6: per-transport throughput and RAM constants
# ---------------------------------------------------------------------------

TRANSPORT_MB_PER_CORE: dict[str, float] = {
    "directsan": 20.0,
    "hotadd":    15.0,
    "nbd":        5.0,
    "auto":      15.0,
}

TRANSPORT_RAM_GB: dict[str, int] = {
    "directsan": 8,
    "hotadd":    8,
    "nbd":       4,
    "auto":      8,
}

# Recommended transport per hypervisor (for validation notes)
_HYPERVISOR_TRANSPORT: dict[str, list[str]] = {
    "vmware":   ["directsan", "hotadd", "nbd", "auto"],
    "hyper-v":  ["hotadd", "nbd", "auto"],
    "ahv":      ["nbd", "auto"],
    "physical": ["nbd", "auto"],
    "mixed":    ["hotadd", "nbd", "auto"],
}


def _resolve_transport(vin: VeeamInput) -> str:
    """
    Determine effective transport mode from input flags and config default.

    Priority:
      1. has_san_access → directsan
      2. on_host_proxy  → hotadd
      3. CONFIG default (if not 'auto') → use as-is
      4. fallback       → nbd
    """
    if vin.has_san_access:
        return "directsan"
    if vin.on_host_proxy:
        return "hotadd"
    cfg_default = str(CONFIG.get("proxy_transport_default", "auto")).lower()
    if cfg_default != "auto":
        return cfg_default
    return "nbd"


def size_proxies(vin: VeeamInput) -> ProxySizing:
    """
    Size proxy concurrency based on daily change rate, backup window,
    and the effective transport mode (Round 6).
    """
    transport = _resolve_transport(vin)
    mb_per_core = TRANSPORT_MB_PER_CORE.get(transport, 15.0)
    ram_per_proxy = TRANSPORT_RAM_GB.get(transport, 8)

    daily_change_tb = vin.total_data_tb * vin.daily_change_percent / 100
    daily_backup_mb = daily_change_tb * 1024 * 1024

    backup_window_sec = vin.backup_window_hours * 3600
    if backup_window_sec <= 0:
        raise ValueError("backup_window_hours must be > 0")

    required_throughput_mb_s = daily_backup_mb / backup_window_sec

    # Use per-transport MB/s/core (overrides the legacy vin.throughput_mb_per_core)
    cores_needed = (required_throughput_mb_s / mb_per_core) * vin.read_write_overhead

    cores_per_proxy = 4
    proxy_count = max(1, math.ceil(cores_needed / cores_per_proxy))

    tasks_per_core = CONFIG["tasks_per_core"]
    total_proxy_cores = proxy_count * cores_per_proxy
    total_parallel_tasks = total_proxy_cores * tasks_per_core
    total_proxy_ram_gb = proxy_count * ram_per_proxy

    # Hypervisor-transport compatibility notes
    notes: list[str] = []
    allowed = _HYPERVISOR_TRANSPORT.get(vin.hypervisor.lower(), [])
    if allowed and transport not in allowed:
        notes.append(
            f"Transport '{transport}' is not recommended for hypervisor "
            f"'{vin.hypervisor}'. Recommended: {', '.join(allowed)}."
        )

    sizing = ProxySizing(
        proxy_count=proxy_count,
        cores_per_proxy=cores_per_proxy,
        total_proxy_cores=total_proxy_cores,
        total_parallel_tasks=total_parallel_tasks,
        required_throughput_mb_s=round(required_throughput_mb_s, 1),
        ram_gb_per_proxy=ram_per_proxy,
        total_proxy_ram_gb=total_proxy_ram_gb,
        transport_mode=transport,
    )
    return sizing


def size_backup_server(proxies: ProxySizing, vin: VeeamInput) -> BackupServerSizing:
    """
    Size the Veeam Backup Server based on workload count, job concurrency,
    indexing, and v13 appliance mode (Round 2).
    """
    workload_count = vin.workload_count if vin.workload_count > 0 else (
        vin.vm_count if vin.vm_count > 0 else proxies.total_proxy_cores * 10
    )

    base_cores = max(4, math.ceil(workload_count / 100))
    concurrency_cores = vin.concurrent_jobs * 2
    total_cores = base_cores + concurrency_cores

    if vin.v13_appliance:
        total_cores = max(8, math.ceil(total_cores * 0.8))

    ram_gb = max(16, total_cores * 2)
    if vin.indexing_enabled:
        ram_gb += math.ceil(workload_count / 50)

    notes: list[str] = []
    if vin.v13_appliance:
        notes.append("v13 appliance mode: consolidated role reduces core requirement by 20%.")
    if vin.indexing_enabled:
        notes.append("Indexing enabled: additional RAM allocated per 50 workloads.")
    if workload_count > 500:
        notes.append(
            f"Large environment ({workload_count} workloads): "
            "consider dedicated catalog/indexing server."
        )

    return BackupServerSizing(
        cores=total_cores,
        ram_gb=ram_gb,
        v13_appliance=vin.v13_appliance,
        notes=notes,
    )


def size_hardened_repo(repo: RepoSizing) -> HardenedRepoHost:
    """
    Size hardened repository hosts.

    Logic:
      - Cap per-host repo usage at ~1 PB (configurable)
      - Recommend 250 TB volumes (configurable)
      - Count hosts needed to stay under cap
    """
    host_cap_tb = float(CONFIG.get("hardened_tb_per_host_cap", 1000.0))
    volume_target_tb = float(CONFIG.get("hardened_volume_tb_target", 250.0))

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
