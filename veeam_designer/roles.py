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
from .platforms import size_platform_workers, uses_platform_workers
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
    "proxmox": ["hotadd", "nbd", "auto"],
    "proxmox_ve": ["hotadd", "nbd", "auto"],
    "pve": ["hotadd", "nbd", "auto"],
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


def _size_hyperv_proxies(
    vin: VeeamInput,
    required_throughput_mb_s: float,
) -> ProxySizing:
    """Size Hyper-V proxies from Veeam throughput guidance plus task minimums."""

    requested_tasks = (
        vin.platform_concurrent_tasks
        if vin.platform_concurrent_tasks > 0
        else max(1, vin.concurrent_jobs)
    )
    max_tasks_per_proxy = max(1, vin.worker_task_limit or 4)

    # Veeam Best Practice says Hyper-V proxy sizing follows the vSphere proxy sizing
    # method. Use the virtual-proxy incremental baseline unless the user supplies a
    # measured override, then enforce Hyper-V task/resource minimums separately.
    if vin.throughput_mb_per_core > 0:
        mb_per_core = vin.throughput_mb_per_core
        throughput_basis = "custom benchmark override"
    else:
        mb_per_core = VMWARE_INCREMENTAL_MB_PER_CORE[("virtual", _proxy_target_storage(vin))]
        throughput_basis = (
            "Veeam Hyper-V BP uses vSphere proxy sizing method; "
            "virtual incremental throughput baseline"
        )

    throughput_core_demand = max(
        1,
        math.ceil((required_throughput_mb_s / mb_per_core) * vin.read_write_overhead),
    )
    task_core_demand = max(1, math.ceil(requested_tasks / 2))
    aggregate_core_demand = max(throughput_core_demand, task_core_demand)

    on_host = vin.on_host_proxy
    if on_host:
        proxy_count = (
            vin.platform_host_count
            if vin.platform_host_count > 0
            else max(1, math.ceil(requested_tasks / max_tasks_per_proxy))
        )
    else:
        proxy_count = max(1, math.ceil(requested_tasks / max_tasks_per_proxy))

    cores_per_proxy = max(2, math.ceil(aggregate_core_demand / proxy_count))
    tasks_per_proxy = max(
        1,
        min(max_tasks_per_proxy, math.ceil(requested_tasks / proxy_count)),
    )

    # Two tasks per core is the documented maximum. If the requested task limit
    # requires more cores than the throughput calculation, raise the per-proxy floor.
    cores_per_proxy = max(cores_per_proxy, math.ceil(tasks_per_proxy / 2))
    total_proxy_cores = proxy_count * cores_per_proxy
    total_parallel_tasks = proxy_count * tasks_per_proxy

    system_min_ram = math.ceil(2 + (0.5 * tasks_per_proxy))
    if on_host:
        # Hyper-V BP notes up to 2 GB RAM per running task on production hosts.
        ram_gb_per_proxy = max(system_min_ram, math.ceil(2.0 * tasks_per_proxy))
    else:
        # Hyper-V BP points to vSphere sizing; retain the 2 GB/core planning
        # allowance while meeting the Hyper-V system minimum.
        ram_gb_per_proxy = max(system_min_ram, cores_per_proxy * 2)

    total_proxy_ram_gb = proxy_count * ram_gb_per_proxy
    estimated_capacity_mb_s = total_proxy_cores * mb_per_core / max(vin.read_write_overhead, 1.0)

    notes = [
        "Hyper-V proxy sizing uses the vSphere proxy sizing method recommended by Veeam Best "
        "Practice, then applies Hyper-V-specific task, CPU, and memory minimums.",
        "Veeam limits backup proxies to no more than 2 concurrent tasks per CPU core.",
        "Hyper-V system requirements specify 2 GB RAM plus 500 MB per concurrent task.",
    ]
    if vin.throughput_mb_per_core <= 0:
        notes.append(
            "No Hyper-V-specific throughput-per-core table is published; the calculator uses "
            "Veeam's virtual vSphere incremental proxy baseline because the Hyper-V Best "
            "Practice Guide explicitly directs proxy sizing to the vSphere method."
        )
    if on_host:
        notes.append(
            "On-host mode is selected. Veeam Best Practice notes that running tasks can require "
            "up to 2 GB RAM each on the Hyper-V host; the calculator uses that stronger planning "
            "allowance and spreads aggregate core demand across the supplied hosts."
        )
    elif vin.has_san_access:
        notes.append(
            "Off-host SAN mode is selected; validate the required transportable VSS hardware "
            "provider for CSV-backed storage."
        )

    return ProxySizing(
        proxy_count=proxy_count,
        cores_per_proxy=cores_per_proxy,
        total_proxy_cores=total_proxy_cores,
        total_parallel_tasks=total_parallel_tasks,
        required_throughput_mb_s=round(required_throughput_mb_s, 1),
        estimated_capacity_mb_s=round(estimated_capacity_mb_s, 1),
        throughput_basis=throughput_basis,
        ram_gb_per_proxy=ram_gb_per_proxy,
        total_proxy_ram_gb=total_proxy_ram_gb,
        transport_mode="on-host" if on_host else "off-host",
        disk_gb_per_proxy=0.3,
        sizing_basis="Veeam Hyper-V BP throughput method plus 13.1.1 system requirements",
        source_url=(
            "https://bp.veeam.com/vbr/2_Design_Structures/D_Veeam_Components/"
            "D_backup_proxies/hyperv_proxies.html"
        ),
        notes=notes,
    )


def _apply_proxy_deployment(
    sizing: ProxySizing,
    vin: VeeamInput,
) -> ProxySizing:
    """Add deployment-platform overhead without changing role throughput capacity."""

    deployment_mode = (vin.proxy_deployment_mode or "managed_os").strip().lower()
    hypervisor = vin.hypervisor.lower()

    if deployment_mode == "infrastructure_appliance":
        if hypervisor != "vmware":
            raise ValueError(
                "Veeam Infrastructure Appliance proxy deployment is modeled only for VMware "
                "backup proxies in this calculator."
            )
        sizing.deployment_mode = deployment_mode
        sizing.allocated_cores_per_proxy = sizing.cores_per_proxy + 2
        sizing.allocated_ram_gb_per_proxy = sizing.ram_gb_per_proxy + 8
        sizing.total_allocated_proxy_cores = sizing.proxy_count * sizing.allocated_cores_per_proxy
        sizing.total_allocated_proxy_ram_gb = sizing.proxy_count * sizing.allocated_ram_gb_per_proxy
        sizing.infrastructure_system_disk_gb = 120
        sizing.infrastructure_data_disk_gb = 120
        sizing.notes.append(
            "Veeam Infrastructure Appliance deployment adds the appliance baseline of 2 vCPU "
            "and 8 GB RAM to each VMware proxy role, plus 120 GB minimum system and "
            "120 GB minimum application-data disks."
        )
        return sizing

    sizing.deployment_mode = "managed_os"
    sizing.allocated_cores_per_proxy = sizing.cores_per_proxy
    sizing.allocated_ram_gb_per_proxy = sizing.ram_gb_per_proxy
    sizing.total_allocated_proxy_cores = sizing.total_proxy_cores
    sizing.total_allocated_proxy_ram_gb = sizing.total_proxy_ram_gb
    return sizing


def size_proxies(vin: VeeamInput) -> ProxySizing:
    """
    Size data-mover resources.

    VMware retains throughput-based proxy sizing, Hyper-V uses native task-based proxy
    requirements, and Proxmox VE / Nutanix AHV use their published worker task models.
    """
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

    if vin.hypervisor.lower() in {"hyperv", "hyper-v"}:
        return _apply_proxy_deployment(
            _size_hyperv_proxies(vin, required_throughput_mb_s),
            vin,
        )

    if uses_platform_workers(vin.hypervisor):
        workers = size_platform_workers(vin)
        if workers is None:
            raise ValueError(f"Worker sizing unavailable for platform {vin.hypervisor!r}")
        sizing = ProxySizing(
            proxy_count=workers.worker_count,
            cores_per_proxy=workers.cores_per_worker,
            total_proxy_cores=workers.total_worker_cores,
            total_parallel_tasks=workers.total_concurrent_tasks,
            required_throughput_mb_s=round(required_throughput_mb_s, 1),
            estimated_capacity_mb_s=0.0,
            throughput_basis=(
                "Veeam platform worker task sizing; no vendor throughput-per-core value applied"
            ),
            ram_gb_per_proxy=workers.ram_gb_per_worker,
            total_proxy_ram_gb=workers.total_worker_ram_gb,
            transport_mode="worker",
            disk_gb_per_proxy=float(workers.disk_gb_per_worker),
            sizing_basis=workers.sizing_basis,
            source_url=workers.source_url,
            deployment_mode="platform_worker",
            allocated_cores_per_proxy=workers.cores_per_worker,
            allocated_ram_gb_per_proxy=workers.ram_gb_per_worker,
            total_allocated_proxy_cores=workers.total_worker_cores,
            total_allocated_proxy_ram_gb=workers.total_worker_ram_gb,
            notes=list(workers.notes),
        )
        if (
            vin.proxy_deployment_mode or "managed_os"
        ).strip().lower() == "infrastructure_appliance":
            raise ValueError(
                "Platform workers are deployed by their virtualization plug-in and are not "
                "Veeam Infrastructure Appliance proxy roles."
            )
        return sizing

    transport = _resolve_transport(vin)
    mb_per_core, throughput_basis = _proxy_throughput_mb_per_core(vin, transport)
    total_proxy_cores = max(
        1,
        math.ceil((required_throughput_mb_s / mb_per_core) * vin.read_write_overhead),
    )

    tasks_per_core = CONFIG["tasks_per_core"]
    proxy_count = max(2, math.ceil(total_proxy_cores / 8))
    cores_per_proxy = max(2, math.ceil(total_proxy_cores / proxy_count))
    total_proxy_cores = proxy_count * cores_per_proxy
    total_parallel_tasks = total_proxy_cores * tasks_per_core
    tasks_per_proxy = cores_per_proxy * tasks_per_core
    ram_per_proxy = max(4, math.ceil(2 + tasks_per_proxy))
    total_proxy_ram_gb = proxy_count * ram_per_proxy
    estimated_capacity_mb_s = total_proxy_cores * mb_per_core / max(vin.read_write_overhead, 1.0)

    notes: list[str] = []
    if transport == "nbd":
        notes.append(
            "NBD throughput is modeled conservatively because Veeam does not publish a dedicated "
            "per-core NBD throughput table in the cited proxy sizing guide."
        )
    if vin.throughput_mb_per_core > 0:
        notes.append(
            "A custom proxy throughput override was supplied and used instead of the built-in "
            "Veeam transport guidance."
        )
    else:
        notes.append(
            "Proxy sizing uses Veeam incremental-throughput guidance and the best-practice target "
            "of up to two proxy tasks per CPU core."
        )
    if vin.hypervisor.lower() == "mixed":
        notes.append(
            "Mixed-environment sizing reuses the VMware proxy throughput model as a planning "
            "heuristic. Validate each platform-specific data mover separately before deployment."
        )
    notes.append(
        "For production availability, Veeam Best Practice recommends at least two proxy servers "
        "per site."
    )

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
        disk_gb_per_proxy=0.75,
        sizing_basis="Veeam VMware incremental proxy guidance",
        source_url="https://bp.veeam.com/vbr/Support/configurations/vmware_proxy.html",
        notes=notes,
    )
    return _apply_proxy_deployment(sizing, vin)


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

    deployment_mode = (vin.deployment_mode or "").strip().lower()
    if not deployment_mode:
        deployment_mode = "software_appliance" if vin.v13_appliance else "windows"

    minimum_ram_gb = max(16, math.ceil(16 + (0.5 * concurrency_hint)))
    minimum_cores = 8
    if deployment_mode == "software_appliance" and workload_count <= 5:
        minimum_cores = 6

    total_cores = max(total_cores, minimum_cores)
    ram_gb = max(ram_gb, minimum_ram_gb)

    system_disk_gb = 0
    secondary_disk_gb = 0
    if deployment_mode == "software_appliance":
        system_disk_gb = 240
        secondary_disk_gb = 240
        notes.append(
            "Veeam Software Appliance minimums are enforced: 8 vCPU (6 for up to 5 workloads), "
            "16 GB RAM plus 500 MB per concurrent job, a 240 GB minimum system disk, and a "
            "second 240 GB minimum application-data disk."
        )
        notes.append(
            "Veeam recommends larger SSD system disks as protected workload count grows "
            "(480 GB for small environments, 960 GB for medium environments, and multi-TB for "
            "large environments). The calculator reports the vendor minimum and leaves the "
            "recommended-capacity choice as an architecture review item."
        )
    else:
        notes.append(
            "Windows backup-server mode selected. The calculator enforces the current 8 vCPU "
            "minimum and 16 GB RAM plus 500 MB per concurrent job in addition to the workload "
            "sizing band."
        )

    return BackupServerSizing(
        cores=total_cores,
        ram_gb=ram_gb,
        v13_appliance=deployment_mode == "software_appliance",
        deployment_mode=deployment_mode,
        system_disk_gb=system_disk_gb,
        secondary_disk_gb=secondary_disk_gb,
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
    platform_workers = size_platform_workers(vin)
    proxies = size_proxies(vin)
    backup_server = size_backup_server(proxies, vin)
    is_object_target = vin.repo_type == "object" or vin.direct_to_object
    hardened = (
        None
        if is_object_target
        else size_hardened_repo(repo, proxies.total_proxy_cores, vin.refs_xfs)
    )

    # Object repositories may use direct data-mover access or a gateway. The current input model
    # does not select between those architectures, so a gateway quantity is not inferred.
    gateways = None

    return RolePlan(
        backup_server=backup_server,
        proxies=proxies,
        platform_workers=platform_workers,
        hardened_repos=hardened,
        gateways=gateways,
    )
