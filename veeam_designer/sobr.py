from __future__ import annotations

from .models import RepoSizing, SobrDesign, VeeamInput


def design_sobr(repo: RepoSizing, vin: VeeamInput) -> SobrDesign:
    """Describe aggregate SOBR tier capacity without inventing storage-platform extent limits."""

    total_repo_tb = max(0.0, repo.total_repo_tb)

    if vin.direct_to_object:
        return SobrDesign(
            extent_count=0,
            extent_size_tb=0.0,
            capacity_tier_tb=round(total_repo_tb, 1),
            archive_tier_tb=0.0,
            recommendation=(
                "Direct-to-object mode: the calculated backup capacity is assigned to object "
                "storage. No performance-tier extent count is inferred."
            ),
        )

    cap_fraction = 0.0
    if vin.capacity_tier_enabled:
        cap_fraction = max(0.0, min(1.0, vin.capacity_tier_fraction))

    capacity_tier_tb = round(total_repo_tb * cap_fraction, 1)
    performance_tier_tb = round(total_repo_tb - capacity_tier_tb, 1)

    if vin.capacity_tier_enabled and cap_fraction <= 0:
        tier_note = (
            "Capacity tier is enabled but no offload fraction was supplied, so no automatic "
            "capacity reduction is assumed."
        )
    elif capacity_tier_tb > 0:
        tier_note = (
            f"User-supplied capacity-tier fraction assigns approximately {capacity_tier_tb:.1f} TB "
            f"({cap_fraction * 100:.0f}%) to object storage."
        )
    else:
        tier_note = "Capacity tier is not included in this design."

    if performance_tier_tb > 0:
        perf_note = (
            f"Aggregate performance-tier capacity requirement is {performance_tier_tb:.1f} TB. "
            "Extent count and extent size depend on the selected storage platform, failure domain, "
            "placement policy, and vendor limits, so the calculator does not invent an extent count."
        )
    else:
        perf_note = "No performance-tier capacity is required by the selected design."

    return SobrDesign(
        extent_count=0,
        extent_size_tb=performance_tier_tb,
        capacity_tier_tb=capacity_tier_tb,
        archive_tier_tb=0.0,
        recommendation=f"{perf_note} {tier_note}",
    )
