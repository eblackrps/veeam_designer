from __future__ import annotations
from .models import SobrDesign, RepoSizing, VeeamInput


def design_sobr(repo: RepoSizing, vin: VeeamInput) -> SobrDesign:
    """
    Design Scale-Out Backup Repository layout.

    Round 5: uses vin.capacity_tier_enabled / capacity_tier_fraction /
    direct_to_object / capacity_tier_immutable to compute actual capacity
    tier TB and adjust performance tier sizing.
    """
    total_repo_tb = repo.total_repo_tb

    # Round 5: direct-to-object bypasses the performance tier entirely
    if vin.direct_to_object:
        extent_count = 0
        extent_size_tb = 0.0
        capacity_tier_tb = round(total_repo_tb, 1)
        archive_tier_tb = 0.0
        rec = (
            "Direct-to-object mode: all backup data written directly to object storage. "
            "No local performance tier required; gateway server(s) act as data movers. "
        )
        if vin.capacity_tier_immutable:
            rec += "Object-lock immutability enabled on capacity tier."
        return SobrDesign(
            extent_count=extent_count,
            extent_size_tb=extent_size_tb,
            capacity_tier_tb=capacity_tier_tb,
            archive_tier_tb=archive_tier_tb,
            recommendation=rec,
        )

    # Compute capacity tier fraction
    if vin.capacity_tier_enabled:
        cap_fraction = max(0.0, min(1.0, vin.capacity_tier_fraction))
    else:
        cap_fraction = 0.0

    capacity_tier_tb = round(total_repo_tb * cap_fraction, 1)
    perf_tier_tb = total_repo_tb - capacity_tier_tb

    # Performance extents sized against the on-disk (performance) portion only
    if perf_tier_tb <= 0:
        extent_count = 0
        extent_size_tb = 0.0
    elif perf_tier_tb <= 150:
        extent_count = 1
        extent_size_tb = round(perf_tier_tb, 1)
    elif perf_tier_tb <= 300:
        extent_count = 2
        extent_size_tb = round(perf_tier_tb / 2, 1)
    elif perf_tier_tb <= 600:
        extent_count = 3
        extent_size_tb = round(perf_tier_tb / 3, 1)
    else:
        extent_count = 4
        extent_size_tb = round(perf_tier_tb / 4, 1)

    archive_tier_tb = 0.0

    if capacity_tier_tb > 0:
        rec = (
            f"Recommend SOBR with {extent_count} performance extent(s) (~{extent_size_tb} TB each), "
            f"and ~{capacity_tier_tb} TB ({int(cap_fraction * 100)}% of total) offloaded to "
            "capacity tier (object storage). "
        )
        if vin.capacity_tier_immutable:
            rec += "Object-lock immutability enabled on capacity tier. "
    else:
        rec = (
            f"Recommend SOBR with {extent_count} performance extent(s) (~{extent_size_tb} TB each). "
            "Capacity tier is not enabled for this design. "
        )

    rec += "Archive tier is optional and not required for this design."

    return SobrDesign(
        extent_count=extent_count,
        extent_size_tb=extent_size_tb,
        capacity_tier_tb=capacity_tier_tb,
        archive_tier_tb=archive_tier_tb,
        recommendation=rec,
    )
