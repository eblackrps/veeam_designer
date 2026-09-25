"""Veeam ONE sizing from current backup-data monitoring guidance."""

from __future__ import annotations

from .models import VeeamOneDesign, VeeamOneInput


def size_veeam_one(vin: VeeamOneInput) -> VeeamOneDesign:
    """Size Veeam ONE for backup-data-only monitoring using published ranges."""

    notes: list[str] = []
    total = max(0, vin.protected_vms) + max(0, vin.protected_physical)
    vbr_servers = max(0, vin.connected_vbr_servers)

    if total <= 1_000:
        base_cores, base_ram = 4, 8
        tier = "up to 1,000 protected workloads"
    elif total <= 10_000:
        base_cores, base_ram = 4, 15
        tier = "1,000-10,000 protected workloads"
    elif total <= 20_000:
        base_cores, base_ram = 6, 30
        tier = "10,000-20,000 protected workloads"
    elif total <= 40_000:
        base_cores, base_ram = 8, 50
        tier = "20,000-40,000 protected workloads"
    elif total <= 60_000:
        base_cores, base_ram = 10, 80
        tier = "40,000-60,000 protected workloads"
    else:
        base_cores, base_ram = 10, 80
        tier = "above the published 60,000-workload range"
        notes.append(
            "Protected workload count exceeds Veeam's published Veeam ONE backup-data sizing "
            "range. Do not extrapolate automatically; validate the deployment with Veeam."
        )

    cores = round(max(4.0, base_cores + (0.03 * vbr_servers)), 2)
    ram_gb = round(max(8.0, base_ram + ((60.0 / 1024.0) * vbr_servers)), 2)

    notes.append(
        f"Veeam ONE backup-data-only sizing uses the conservative upper end of the published "
        f"{tier} range, with 0.03 vCPU and 60 MB RAM added per connected VBR server. "
        "Fractional requirements are preserved instead of rounded into whole vCPUs/GB."
    )
    notes.append(
        "Database capacity is intentionally not estimated from a made-up per-VM rate. Use the "
        "Veeam ONE Database Calculator for SQL application-data sizing."
    )

    em_cores = 0
    em_ram = 0
    if vin.enterprise_manager:
        em_cores, em_ram = 4, 16
        notes.append(
            "Enterprise Manager uses Veeam's recommended Linux appliance resources: "
            "4 vCPU / 16 GB RAM. Windows deployments have different minimum wording."
        )

    vspc_cores = 0
    if vin.vspc_tenants > 0:
        notes.append(
            "VSPC is a separate product and is not sized from Veeam ONE workload counts. "
            "No VSPC CPU estimate is emitted; use the current VSPC sizing guide."
        )

    return VeeamOneDesign(
        server_cores=cores,
        server_ram_gb=ram_gb,
        database_size_gb=0,
        em_cores=em_cores,
        em_ram_gb=em_ram,
        vspc_cores=vspc_cores,
        notes=notes,
    )
