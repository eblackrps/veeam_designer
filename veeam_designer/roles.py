from __future__ import annotations

import math

from .config import CONFIG
from .models import (
    BackupServerSizing,
    GatewayServerSizing,
    HardenedRepoHost,
    ProxySizing,
    RepoSizing,
    RolePlan,
    VeeamInput,
)
from .workload_math import projected_daily_change_tb, tb_to_mb

VMWARE_INCREMENTAL_MB_PER_CORE: dict[tuple[str, str], float] = {
    ("virtual", "block"): 80.0,
    ("virtual", "object"): 80.0,
    ("physical", "block"): 250.0,
    ("physical", "object"): 150.0,
}
NBD_HEURISTIC_MB_PER_CORE = 40.0

# Recommended transport per hypervisor (for validation notes)
_HYPERVISOR_TRANSPORT: dict[str, list[str]] = {
    "vmware": ["directsan", "hotadd", "nbd", "auto"],
    "hyper-v": ["hotadd", "nbd", "auto"],
    "hyperv": ["hotadd", "nbd", "auto"],
    "ahv": ["nbd", "auto"],
    "nutanix_ahv": ["nbd", "auto"],
    "physical": ["nbd", "auto"],
    "mixed": ["hotadd", "nbd", "auto"],
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


def _proxy_target_storage(vin: VeeamInput) -> str:
    if vin.repo_type == "object" or vin.direct_to_object:
        return "object"
    return "block"


def _proxy_type_for_transport(transport: str) -> str:
    return "physical" if transport == "directsan" else "virtual"


def _proxy_throughput_mb_per_core(vin: VeeamInput, transport: str) -> tuple[float, str]:
    if vin.throughput_mb_per_core > 0:
        return vin.throughput_mb_per_core, "custom benchmark override"
    if transport == "nbd":
        return NBD_HEURISTIC_MB_PER_CORE, "conservative NBD heuristic"
    return (
        VMWARE_INCREMENTAL_MB_PER_CORE[
            (_proxy_type_for_transport(transport), _proxy_target_storage(vin))
        ],
        "Veeam VMware incremental proxy guidance",
    )


def size_proxies(vin: VeeamInput) -> ProxySizing:
    """
    Size proxy resources using Veeam published throughput guidance where available.
    """
    transport = _resolve_transport(vin)
    mb_per_core, throughput_basis = _proxy_throughput_mb_per_core(vin, transport)

    daily_change_size_tb = projected_daily_change_tb(
        total_data_tb=vin.total_data_tb,
        daily_change_percent=vin.daily_change_percent,
        annual_growth_percent=vin.annual_growth_percent,
        years_to_plan_for=vin.years_to_plan_for,
    )
    daily_backup_mb = tb_to_mb(daily_change_size_tb)

    backup_window_sec = vin.backup_window_hours * 3600
    if backup_window_sec <= 0:
        raise ValueError("backup_window_hours must be > 0")

    required_throughput_mb_s = daily_backup_mb / backup_window_sec
    total_proxy_cores = max(
        1,
        math.ceil((required_throughput_mb_s / mb_per_core) * vin.read_write_overhead),
    )

    tasks_per_core = CONFIG["tasks_per_core"]
    proxy_count = max(2, math.ceil(total_proxy_cores / 8))
    cores_per_proxy = max(2, math.ceil(total_proxy_cores / proxy_count))
    total_proxy_cores = proxy_count * cores_per_proxy
    total_parallel_tasks = total_proxy_cores * tasks_per_core
    total_proxy_ram_gb = total_proxy_cores * 2
    ram_per_proxy = max(4, math.ceil(total_proxy_ram_gb / proxy_count))
    estimated_capacity_mb_s = total_proxy_cores * mb_per_core / max(vin.read_write_overhead, 1.0)

    # Hypervisor-transport compatibility notes
    notes: list[str] = []
    allowed = _HYPERVISOR_TRANSPORT.get(vin.hypervisor.lower(), [])
    if allowed and transport not in allowed:
        notes.append(
            f"Transport '{transport}' is not recommended for hypervisor "
            f"'{vin.hypervisor}'. Recommended: {', '.join(allowed)}."
        )
    if transport == "nbd":
        notes.append(
            "NBD transport throughput is modeled conservatively because Veeam does not publish a "
            "separate per-core NBD throughput table in the cited sizing guide."
        )
    if vin.throughput_mb_per_core > 0:
        notes.append(
            "A custom proxy throughput override was supplied. The calculator used that value "
            "instead of the built-in Veeam transport guidance."
        )
    else:
        notes.append(
            "Proxy sizing uses Veeam vSphere proxy incremental-throughput guidance and keeps the "
            "best-practice target of two proxy tasks per CPU core."
        )
    if vin.hypervisor.lower() != "vmware" and vin.throughput_mb_per_core <= 0:
        notes.append(
            "Hyper-V, AHV, and mixed-environment proxy throughput still reuse the VMware transport "
            "table as a planning heuristic unless you provide a custom throughput override."
        )
    notes.append("The calculator recommends at least two proxy servers per site for availability.")

    sizing = ProxySizing(
        proxy_count=proxy_count,
        cores_per_proxy=cores_per_proxy,
        total_proxy_cores=total_proxy_cores,
        total_parallel_tasks=total_parallel_tasks,
        required_throughput_mb_s=round(required_throughput_mb_s, 1),
        estimated_capacity_mb_s=round(estimated_capacity_mb_s, 1),
        throughput_basis=throughput_basis,
        ram_gb_per_proxy=ram_per_proxy,
        total_proxy_ram_gb=total_proxy_ram_gb,
        transport_mode=transport,
    )
    return sizing


def size_backup_server(proxies: ProxySizing, vin: VeeamInput) -> BackupServerSizing:
    """
    Size the Veeam backup server from Veeam best-practice workload bands.
    """
    workload_count = (
        vin.workload_count
        if vin.workload_count > 0
        else (vin.vm_count if vin.vm_count > 0 else proxies.total_proxy_cores * 10)
    )
    workload_bands = [
        (500, 50, 12, 24),
        (1000, 100, 24, 32),
        (5000, 500, 48, 64),
        (10000, 1000, 56, 128),
    ]
    concurrency_hint = max(1, vin.concurrent_jobs)

    total_cores = 56
    ram_gb = 128
    for max_workloads, max_concurrent_tasks, band_cores, band_ram in workload_bands:
        if workload_count <= max_workloads and concurrency_hint <= max_concurrent_tasks:
            total_cores = band_cores
            ram_gb = band_ram
            break
    else:
        extra_units = math.ceil(max(0, workload_count - 10000) / 2000)
        total_cores += extra_units * 8
        ram_gb += extra_units * 16

    if vin.indexing_enabled:
        ram_gb += 8

    notes: list[str] = []
    notes.append(
        "Backup server sizing uses Veeam initial sizing recommendation bands for VMware and "
        "physical-machine backup environments."
    )
    if vin.indexing_enabled:
        notes.append("Guest indexing is enabled; extra RAM was added above the baseline band.")
    if workload_count > 10000:
        notes.append(
            "This environment exceeds the published 10,000-workload backup-server table. The "
            "calculator extends the largest Veeam band linearly and should be reviewed manually."
        )
    if vin.nas_input or vin.replication_input or vin.tape_input:
        notes.append(
            "Additional workload types are present. Veeam recommends consulting a technical "
            "advisor when sizing beyond VMware and physical-machine backup alone."
        )
    notes.append("Always verify against the current Veeam system requirements minimums.")

    return BackupServerSizing(
        cores=total_cores,
        ram_gb=ram_gb,
        v13_appliance=vin.v13_appliance,
        notes=notes,
    )


def size_hardened_repo(
    repo: RepoSizing, proxy_total_cores: int, refs_xfs: bool
) -> HardenedRepoHost:
    """
    Size repository hosts from Veeam repository compute guidance.
    """
    host_cap_tb = float(CONFIG.get("hardened_tb_per_host_cap", 1000.0))
    volume_target_tb = float(CONFIG.get("hardened_volume_tb_target", 250.0))

    host_count = max(1, math.ceil(repo.total_repo_tb / host_cap_tb))
    tb_per_host = repo.total_repo_tb / host_count
    total_repo_cores = max(2, math.ceil(proxy_total_cores / 3))
    total_repo_ram_gb = max(8, total_repo_cores * 4)
    cpu_cores_each = max(2, math.ceil(total_repo_cores / host_count))
    ram_gb_each = max(8, math.ceil(total_repo_ram_gb / host_count))

    notes = (
        f"Hardened repo host capped at ~{host_cap_tb:.0f} TB per host. "
        f"Recommended volume/extent size ~{volume_target_tb:.0f} TB. "
        "Repository compute follows Veeam guidance of one repository core per three proxy cores "
        "and 4 GB RAM per repository core. "
        "Use XFS/ReFS with immutability, separate mgmt/data NICs, "
        "and avoid domain-joining hardened hosts."
    )
    if refs_xfs:
        notes += (
            " For large ReFS/XFS volumes, review Veeam guidance that recommends additional memory "
            "for filesystem metadata overhead."
        )

    return HardenedRepoHost(
        count=host_count,
        tb_per_host=round(tb_per_host, 1),
        cpu_cores_each=cpu_cores_each,
        ram_gb_each=ram_gb_each,
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
    hardened = size_hardened_repo(repo, proxies.total_proxy_cores, vin.refs_xfs)

    # Gateways ONLY for repo_type == object
    gateways = size_gateways(repo) if vin.repo_type == "object" else None

    return RolePlan(
        backup_server=backup_server,
        proxies=proxies,
        hardened_repos=hardened,
        gateways=gateways,
    )
