"""Veeam license-consumption planning without invented commercial pricing."""

from __future__ import annotations

from math import floor

from .models import LicenseEstimate, LicenseInput


def estimate_license(lin: LicenseInput) -> LicenseEstimate:
    """Estimate license units from current Veeam consumption rules."""

    notes: list[str] = []
    license_type = (lin.license_type or "vul").strip().lower()
    if license_type == "vul":
        license_type = "instance"
    if license_type not in {"instance", "capacity", "socket"}:
        raise ValueError("license_type must be instance/vul, capacity, or socket")

    machine_instances = max(0, lin.vm_count) + max(0, lin.physical_count) + max(
        0, lin.cloud_workloads
    )

    # Veeam rounds each unstructured source down to 500 GB for instance licensing.
    # The calculator only receives aggregate NAS TB, so this is an aggregate-source estimate.
    nas_instance_consumption = floor(max(0.0, lin.nas_tb) / 0.5)
    instance_consumption = float(machine_instances + nas_instance_consumption)

    # Capacity licensing consumes 1 TB chunks and rounds each source down to 1 TB.
    capacity_consumption_tb = float(floor(max(0.0, lin.nas_tb)))

    estimated_sockets = max(0, lin.occupied_sockets)
    annual_usd = 0.0

    if license_type == "instance":
        tier = "instance"
        protected_workloads = int(instance_consumption)
        notes.append(
            f"Estimated instance consumption: {protected_workloads} instance(s). "
            "VM, physical, and cloud counts are treated as one instance each in this generic "
            "planner; workload edition-specific exceptions must be checked against the contract."
        )
        if lin.nas_tb > 0:
            notes.append(
                f"Aggregate unstructured-data estimate: {lin.nas_tb:.2f} TB -> "
                f"{nas_instance_consumption} instance(s) at one instance per 500 GB after "
                "rounding down. Veeam rounds per data source, so source-level inventory can "
                "produce a different total."
            )
    elif license_type == "capacity":
        tier = "capacity"
        protected_workloads = machine_instances
        notes.append(
            f"Estimated unstructured capacity consumption: {capacity_consumption_tb:.0f} TB "
            "after aggregate 1 TB rounding-down."
        )
        if machine_instances:
            notes.append(
                "Capacity licensing covers unstructured source data, not VM/physical/cloud "
                "workloads. Those workloads require an applicable instance or socket entitlement."
            )
    else:
        tier = "socket"
        protected_workloads = machine_instances
        if estimated_sockets:
            notes.append(
                f"Socket requirement uses the supplied {estimated_sockets} occupied source-host "
                "motherboard socket(s). Target hosts are not counted."
            )
        else:
            notes.append(
                "Socket count was not supplied, so no socket quantity is estimated. Veeam "
                "requires a license for every occupied motherboard socket on protected source "
                "hosts; VM count cannot be converted reliably into sockets."
            )
        notes.append("Socket licensing is not available with a Linux-based backup server.")

    notes.append(
        "Commercial license pricing is intentionally not estimated. Veeam pricing, editions, "
        "packages, discounts, and contract terms are not a stable sizing formula."
    )

    return LicenseEstimate(
        protected_workloads=protected_workloads,
        estimated_sockets=estimated_sockets,
        tier=tier,
        annual_maintenance_usd=annual_usd,
        instance_consumption=round(instance_consumption, 1),
        capacity_consumption_tb=round(capacity_consumption_tb, 1),
        notes=notes,
    )
