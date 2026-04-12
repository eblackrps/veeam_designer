"""Veeam license tier estimation (VUL — Universal License)."""

from __future__ import annotations

from math import ceil

from .config import CONFIG
from .models import LicenseEstimate, LicenseInput


def estimate_license(lin: LicenseInput) -> LicenseEstimate:
    """Estimate Veeam VUL workload count, tier, and annual maintenance cost."""
    notes = []

    nas_equiv = ceil(lin.nas_tb) if lin.nas_tb > 0 else 0
    total = lin.vm_count + lin.physical_count + nas_equiv + lin.cloud_workloads

    if total < 10:
        tier = "community"
        rate = 0.0
        notes.append("Community Edition: free up to 10 workloads — no Enterprise features.")
    elif total < 500:
        tier = "standard"
        rate = float(CONFIG.get("vul_price_per_instance_usd", 150.0))
        notes.append(
            f"Standard tier: {total} protected workloads at ~${rate:.0f}/instance/yr list price."
        )
    else:
        tier = "enterprise"
        rate = float(CONFIG.get("vul_enterprise_price_usd", 120.0))
        notes.append(
            f"Enterprise tier: {total} workloads — volume pricing applies (~${rate:.0f}/instance/yr)."
        )

    annual_usd = round(total * rate, 2)
    estimated_sockets = max(1, ceil(lin.vm_count / 10))

    if lin.nas_tb > 0:
        notes.append(
            f"NAS: {lin.nas_tb:.0f} TB counted as {nas_equiv} VUL instances (1 TB = 1 instance)."
        )
    if lin.physical_count > 0:
        notes.append(f"Physical servers: {lin.physical_count} counted at 1 VUL instance each.")
    if lin.license_type == "socket":
        notes.append(
            f"Socket estimate: ~{estimated_sockets} sockets ({lin.vm_count} VMs / 10 per socket)."
        )

    return LicenseEstimate(
        protected_workloads=total,
        estimated_sockets=estimated_sockets,
        tier=tier,
        annual_maintenance_usd=annual_usd,
        notes=notes,
    )
