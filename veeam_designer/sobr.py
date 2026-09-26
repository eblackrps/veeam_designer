from __future__ import annotations

from .models import RepoSizing, SobrDesign, VeeamInput


def design_sobr(repo: RepoSizing, vin: VeeamInput) -> SobrDesign:
    """Design performance/capacity tier allocation from explicit policy assumptions."""

    total_repo_tb = repo.total_repo_tb
    is_object_target = vin.direct_to_object or vin.repo_type == "object"

    if is_object_target:
        return SobrDesign(
            extent_count=0,
            extent_size_tb=0.0,
            capacity_tier_tb=round(total_repo_tb, 1),
            archive_tier_tb=0.0,
            recommendation=(
                "Object-target mode: all modeled backup capacity is assigned to object storage. "
                "No local performance tier is included in this design."
            ),
            performance_tier_tb=0.0,
            moved_to_capacity_tb=round(total_repo_tb, 1),
            capacity_tier_policy="direct",
        )

    policy = (vin.capacity_tier_policy or "move").strip().lower()
    if policy not in {"move", "copy", "copy_move"}:
        raise ValueError("capacity_tier_policy must be 'move', 'copy', or 'copy_move'")

    requested_policy = policy
    forever_forward_move_ignored = (
        vin.capacity_tier_enabled
        and vin.backup_type in {"forever_forward_incremental", "forever_forward"}
        and policy in {"move", "copy_move"}
    )
    if forever_forward_move_ignored:
        policy = "copy"

    cap_fraction = (
        max(0.0, min(1.0, vin.capacity_tier_fraction)) if vin.capacity_tier_enabled else 0.0
    )
    tier_eligible_tb = max(0.0, repo.short_term_data_tb + repo.gfs_repo_tb)

    moved_tb = 0.0
    object_tb = 0.0

    if vin.capacity_tier_enabled:
        if policy == "move":
            moved_tb = round(tier_eligible_tb * cap_fraction, 1)
            object_tb = moved_tb
            performance_tb = total_repo_tb - moved_tb
            rec = (
                f"Capacity Tier Move: ~{moved_tb} TB "
                f"({int(cap_fraction * 100)}% of retained/GFS data) is modeled as moved "
                "from local performance storage to object storage. Operational transformation "
                "headroom remains local."
            )
        elif policy == "copy":
            object_tb = round(tier_eligible_tb, 1)
            performance_tb = total_repo_tb
            rec = (
                f"Capacity Tier Copy: ~{object_tb} TB of retained/GFS data is modeled as "
                "copied to object storage while the full local performance-tier footprint remains."
            )
        else:
            moved_tb = round(tier_eligible_tb * cap_fraction, 1)
            object_tb = round(tier_eligible_tb, 1)
            performance_tb = total_repo_tb - moved_tb
            rec = (
                f"Capacity Tier Copy + Move: ~{object_tb} TB of retained/GFS data is modeled "
                f"in object storage, while ~{moved_tb} TB "
                f"({int(cap_fraction * 100)}%) is modeled as aged out of local performance storage."
            )
    else:
        performance_tb = total_repo_tb
        rec = "Capacity tier is not enabled for this design."

    performance_tb = max(0.0, performance_tb)

    if forever_forward_move_ignored:
        rec += (
            f" Requested policy '{requested_policy}' includes Move, but Veeam ignores Move for "
            "forever-forward incremental chains and applies Copy behavior because the chain "
            "remains active."
        )

    if vin.capacity_tier_immutable and object_tb > 0:
        rec += " Object-lock immutability is enabled on the capacity tier."

    if performance_tb <= 0:
        extent_count = 0
        extent_size_tb = 0.0
    elif performance_tb <= 150:
        extent_count = 1
        extent_size_tb = round(performance_tb, 1)
    elif performance_tb <= 300:
        extent_count = 2
        extent_size_tb = round(performance_tb / 2, 1)
    elif performance_tb <= 600:
        extent_count = 3
        extent_size_tb = round(performance_tb / 3, 1)
    else:
        extent_count = 4
        extent_size_tb = round(performance_tb / 4, 1)

    rec += " Archive tier is optional and not required for this design."

    return SobrDesign(
        extent_count=extent_count,
        extent_size_tb=extent_size_tb,
        capacity_tier_tb=round(object_tb, 1),
        archive_tier_tb=0.0,
        recommendation=rec,
        performance_tier_tb=round(performance_tb, 1),
        moved_to_capacity_tb=round(moved_tb, 1),
        capacity_tier_policy=policy if vin.capacity_tier_enabled else "none",
    )
