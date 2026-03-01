from __future__ import annotations
from .models import SobrDesign, RepoSizing


def design_sobr(
    repo: RepoSizing,
    capacity_tier_fraction: float = 0.0,   # default: NO capacity tier unless explicitly enabled
    archive_fraction: float = 0.0,         # default: NO archive tier
) -> SobrDesign:
    total_repo_tb = repo.total_repo_tb

    # Determine number of performance extents
    if total_repo_tb <= 150:
        extent_count = 1
    elif total_repo_tb <= 300:
        extent_count = 2
    elif total_repo_tb <= 600:
        extent_count = 3
    else:
        extent_count = 4

    # Performance extent sizing
    extent_size_tb = round(total_repo_tb / extent_count, 1)

    # Capacity tier (object storage) and archive tier
    capacity_tier_tb = round(total_repo_tb * capacity_tier_fraction, 1)
    archive_tier_tb = round(total_repo_tb * archive_fraction, 1)

    # Build recommendation text
    if capacity_tier_tb > 0:
        rec = (
            f"Recommend SOBR with {extent_count} performance extents (~{extent_size_tb} TB each), "
            f"and ~{capacity_tier_tb} TB offloaded to capacity tier (object storage). "
        )
    else:
        rec = (
            f"Recommend SOBR with {extent_count} performance extents (~{extent_size_tb} TB each). "
            "Capacity tier is not enabled for this design. "
        )

    if archive_tier_tb > 0:
        rec += f"Archive tier sized at ~{archive_tier_tb} TB for long-term retention."
    else:
        rec += "Archive tier is optional and not required for this design."

    # Return SOBR design structure
    return SobrDesign(
        extent_count=extent_count,
        extent_size_tb=extent_size_tb,
        capacity_tier_tb=capacity_tier_tb,
        archive_tier_tb=archive_tier_tb,
        recommendation=rec,
    )
