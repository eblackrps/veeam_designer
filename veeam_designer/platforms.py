from __future__ import annotations

import math

from .models import PlatformWorkerSizing, VeeamInput

PROXMOX_SOURCE = "https://helpcenter.veeam.com/docs/vbr/userguide/pve_system_requirements.html"
AHV_SOURCE = "https://helpcenter.veeam.com/docs/vbr/userguide/ahv_system_requirements.html"

_PLATFORM_ALIASES = {
    "proxmox": "proxmox",
    "proxmox_ve": "proxmox",
    "pve": "proxmox",
    "ahv": "ahv",
    "nutanix_ahv": "ahv",
}


def canonical_platform(value: str) -> str:
    return _PLATFORM_ALIASES.get((value or "").strip().lower(), (value or "").strip().lower())


def uses_platform_workers(value: str) -> bool:
    return canonical_platform(value) in {"proxmox", "ahv"}


def size_platform_workers(vin: VeeamInput) -> PlatformWorkerSizing | None:
    """Size Veeam plug-in workers for platforms that use the worker architecture."""

    platform = canonical_platform(vin.hypervisor)
    if platform not in {"proxmox", "ahv"}:
        return None

    requested_tasks = (
        vin.platform_concurrent_tasks
        if vin.platform_concurrent_tasks > 0
        else max(1, vin.concurrent_jobs)
    )
    tasks_per_worker = max(1, vin.worker_task_limit or 4)
    worker_count = max(1, math.ceil(requested_tasks / tasks_per_worker))

    if vin.platform_cluster_count > 0:
        worker_count = max(worker_count, vin.platform_cluster_count)

    extra_tasks = max(0, tasks_per_worker - 4)
    cores_per_worker = 6 + extra_tasks
    ram_gb_per_worker = 6 + extra_tasks
    disk_gb_per_worker = 100

    if platform == "proxmox":
        source_url = PROXMOX_SOURCE
        transport_modes = ["hotadd", "nbd"]
        notes = [
            "Veeam Proxmox workers default to 6 vCPU, 6 GB RAM and 100 GB disk for 4 concurrent tasks.",
            "Each task above the default four adds 1 vCPU and 1 GB RAM to each worker.",
            "Veeam creates a processing task per protected Proxmox VM; storage-level backup-operation limits can reduce effective concurrency.",
        ]
        if vin.platform_host_count > 0 and worker_count < vin.platform_host_count:
            notes.append(
                f"The design has {vin.platform_host_count} Proxmox hosts but {worker_count} workers. "
                "Veeam best practice recommends at least one worker per host for Hot-Add coverage; "
                "VMs without a same-host worker can be processed over NBD."
            )
    else:
        source_url = AHV_SOURCE
        transport_modes = ["platform-native worker"]
        notes = [
            "Veeam Nutanix AHV workers default to 6 vCPU, 6 GB RAM and 100 GB disk for 4 concurrent tasks.",
            "Each task above the default four adds 1 vCPU and 1 GB RAM to each worker.",
            "Veeam recommends worker coverage in each AHV cluster and recommends not configuring more workers than cluster hosts.",
            "AHV best practice also recommends that total worker task limits in a cluster do not exceed the cluster physical-disk count; disk count is not yet collected by this calculator.",
        ]
        if vin.platform_host_count > 0 and worker_count > vin.platform_host_count:
            notes.append(
                f"Calculated worker count ({worker_count}) exceeds the supplied AHV host count "
                f"({vin.platform_host_count}); review concurrency or worker task limits."
            )

    if vin.platform_host_count <= 0:
        notes.append(
            "Host count was not supplied, so host-placement and affinity guidance is not validated."
        )

    return PlatformWorkerSizing(
        platform=platform,
        worker_count=worker_count,
        tasks_per_worker=tasks_per_worker,
        total_concurrent_tasks=worker_count * tasks_per_worker,
        cores_per_worker=cores_per_worker,
        ram_gb_per_worker=ram_gb_per_worker,
        disk_gb_per_worker=disk_gb_per_worker,
        total_worker_cores=worker_count * cores_per_worker,
        total_worker_ram_gb=worker_count * ram_gb_per_worker,
        transport_modes=transport_modes,
        sizing_basis="Veeam 13.1.1 worker system requirements",
        source_url=source_url,
        notes=notes,
    )
