"""Veeam ONE monitoring server and Enterprise Manager sizing."""
from __future__ import annotations
from math import ceil
from .models import VeeamOneInput, VeeamOneDesign


def size_veeam_one(vin: VeeamOneInput) -> VeeamOneDesign:
    """Size Veeam ONE server, database, EM, and VSPC based on workload count."""
    notes = []
    total = vin.protected_vms + vin.protected_physical

    if total <= 500:
        cores, ram = 4, 8
        notes.append("Small deployment (<500 workloads): Veeam ONE on 4 cores / 8 GB RAM.")
    elif total <= 2000:
        cores, ram = 8, 16
        notes.append("Medium deployment (500-2000): Veeam ONE on 8 cores / 16 GB RAM.")
    elif total <= 5000:
        cores, ram = 16, 32
        notes.append("Large deployment (2000-5000): Veeam ONE on 16 cores / 32 GB RAM.")
    else:
        cores, ram = 32, 64
        notes.append("Extra-large (>5000): Veeam ONE on 32 cores / 64 GB RAM — consider distributed mode.")

    # DB: ~5 MB/VM/day * retention
    db_gb = max(20, ceil(total * 5 / 1024.0 * vin.retention_days))

    em_cores = 4 if vin.enterprise_manager else 0
    em_ram = 8 if vin.enterprise_manager else 0
    if vin.enterprise_manager:
        notes.append("Enterprise Manager: 4 cores / 8 GB RAM (add SQL Server separately).")

    vspc_cores = max(0, ceil(vin.vspc_tenants / 50) * 4) if vin.vspc_tenants > 0 else 0
    if vin.vspc_tenants > 0:
        notes.append(
            f"VSPC for {vin.vspc_tenants} tenants: ~{vspc_cores} cores "
            f"(1 VSPC node per 50 tenants x 4 cores)."
        )

    return VeeamOneDesign(
        server_cores=cores,
        server_ram_gb=ram,
        database_size_gb=db_gb,
        em_cores=em_cores,
        em_ram_gb=em_ram,
        vspc_cores=vspc_cores,
        notes=notes,
    )
