from __future__ import annotations

from .models import RepoSizing, SobrDesign, VeeamInput
from .workload_math import projected_daily_change_tb, projected_total_data_tb


def _normalized_backup_type(value: str) -> str:
    backup_type = (value or "synthetic_full_weekly").strip().lower()
    return {
        "forever_forward": "forever_forward_incremental",
        "active_full": "active_full_weekly",
    }.get(backup_type, backup_type)


def _effective_retention_days(vin: VeeamInput) -> int:
    retention_days = max(0, int(vin.primary_retention_days))
    if vin.immutability_enabled and vin.immutability_days > 0:
        retention_days = max(retention_days, int(vin.immutability_days))
    return retention_days


def _move_eligible_short_term_tb(repo: RepoSizing, vin: VeeamInput) -> tuple[float, int, str]:
    """Estimate physical short-term data eligible for automatic Capacity Tier Move.

    The model is intentionally conservative:
    - only restore points in sealed weekly forward-incremental chains are eligible
    - the newest seven daily restore points are treated as the active chain
    - restore points must be strictly older than the operational restore window
    - Fast Clone synthetic fulls receive only changed-block reclaim credit because shared
      baseline blocks may still be referenced by the active local chain
    - GFS points are not credited as moved because their actual ages are not represented
      by the current input model
    """

    orw_days = max(0, int(vin.capacity_tier_operational_restore_days))
    backup_type = _normalized_backup_type(vin.backup_type)

    if backup_type == "forever_forward_incremental":
        return (
            0.0,
            0,
            "Forever-forward incremental has no inactive short-term chain. Veeam ignores Move "
            "and applies Copy behavior unless a new full/GFS event seals the chain.",
        )

    if backup_type == "reverse_incremental":
        return (
            0.0,
            0,
            "Reverse-incremental Move receives no automatic local-capacity credit because the "
            "current input model does not define a periodic full that would seal an inactive chain.",
        )

    if backup_type not in {"synthetic_full_weekly", "active_full_weekly"}:
        return 0.0, 0, f"No Capacity Tier Move model is defined for {backup_type!r}."

    reduction_ratio = max(0.01, vin.compression_ratio * vin.dedupe_ratio)
    full_physical_tb = (
        projected_total_data_tb(
            total_data_tb=vin.total_data_tb,
            annual_growth_percent=vin.annual_growth_percent,
            years_to_plan_for=vin.years_to_plan_for,
        )
        / reduction_ratio
    )
    incremental_physical_tb = (
        projected_daily_change_tb(
            total_data_tb=vin.total_data_tb,
            daily_change_percent=vin.daily_change_percent,
            annual_growth_percent=vin.annual_growth_percent,
            years_to_plan_for=vin.years_to_plan_for,
        )
        / reduction_ratio
    )

    daily_restore_points = max(3, _effective_retention_days(vin) + 1)
    weekly_chain_days = 7
    max_forward_points = daily_restore_points + (weekly_chain_days - 1)

    # Conservative steady-state phase: ages 0-6 are the newest active weekly chain.
    inactive_ages = range(weekly_chain_days, max_forward_points)
    eligible_ages = [age for age in inactive_ages if age > orw_days]
    if not eligible_ages:
        return (
            0.0,
            0,
            f"No sealed short-term restore point is older than the {orw_days}-day operational "
            "restore window in the modeled weekly chain.",
        )

    fast_clone = backup_type == "synthetic_full_weekly" and vin.refs_xfs
    if fast_clone:
        moved_tb = incremental_physical_tb * len(eligible_ages)
        basis = (
            f"{len(eligible_ages)} sealed restore point(s) are older than the {orw_days}-day "
            "operational restore window. Fast Clone reclaim is conservatively credited at "
            "changed-block size only; shared full blocks remain local while referenced."
        )
    else:
        moved_tb = 0.0
        full_points = 0
        incremental_points = 0
        for age in eligible_ages:
            if (age + 1) % weekly_chain_days == 0:
                moved_tb += full_physical_tb
                full_points += 1
            else:
                moved_tb += incremental_physical_tb
                incremental_points += 1
        basis = (
            f"{len(eligible_ages)} sealed restore point(s) are older than the {orw_days}-day "
            f"operational restore window: {full_points} full and {incremental_points} incremental "
            "physical backup file(s) in the conservative weekly-chain phase."
        )

    moved_tb = min(max(0.0, moved_tb), max(0.0, repo.short_term_data_tb))
    return round(moved_tb, 1), len(eligible_ages), basis


def _extent_layout(performance_tb: float) -> tuple[int, float]:
    if performance_tb <= 0:
        return 0, 0.0
    if performance_tb <= 150:
        return 1, round(performance_tb, 1)
    if performance_tb <= 300:
        return 2, round(performance_tb / 2, 1)
    if performance_tb <= 600:
        return 3, round(performance_tb / 3, 1)
    return 4, round(performance_tb / 4, 1)


def design_sobr(repo: RepoSizing, vin: VeeamInput) -> SobrDesign:
    """Design performance/capacity tier allocation from Veeam policy semantics."""

    total_repo_tb = repo.total_repo_tb
    is_object_target = vin.direct_to_object or vin.repo_type == "object"
    orw_days = max(0, int(vin.capacity_tier_operational_restore_days))

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
            operational_restore_window_days=0,
            move_eligible_short_term_tb=round(total_repo_tb, 1),
            move_model_basis="Direct object target; Capacity Tier operational restore window is not applicable.",
        )

    policy = (vin.capacity_tier_policy or "move").strip().lower()
    if policy not in {"move", "copy", "copy_move"}:
        raise ValueError("capacity_tier_policy must be 'move', 'copy', or 'copy_move'")

    retained_copy_tb = max(0.0, repo.short_term_data_tb + repo.gfs_repo_tb)
    moved_tb, _eligible_points, move_basis = _move_eligible_short_term_tb(repo, vin)

    backup_type = _normalized_backup_type(vin.backup_type)
    has_gfs = any(
        count > 0
        for count in (vin.gfs_weekly_count, vin.gfs_monthly_count, vin.gfs_yearly_count)
    )
    forever_forward_move_ignored = (
        vin.capacity_tier_enabled
        and backup_type == "forever_forward_incremental"
        and not has_gfs
        and policy in {"move", "copy_move"}
    )
    forever_forward_gfs_uncredited = (
        vin.capacity_tier_enabled
        and backup_type == "forever_forward_incremental"
        and has_gfs
        and policy in {"move", "copy_move"}
    )
    reverse_move_uncredited = (
        vin.capacity_tier_enabled
        and backup_type == "reverse_incremental"
        and policy in {"move", "copy_move"}
    )

    object_tb = 0.0
    performance_tb = total_repo_tb
    rec = "Capacity tier is not enabled for this design."

    if vin.capacity_tier_enabled:
        if forever_forward_move_ignored:
            # Veeam explicitly applies Copy behavior to a forever-forward active chain.
            object_tb = retained_copy_tb
            moved_tb = 0.0
            performance_tb = total_repo_tb
            policy = "copy"
            rec = (
                "Capacity Tier Move is ignored for the forever-forward active chain; Veeam applies "
                "Copy behavior. The modeled retained/GFS backup footprint is copied to object "
                "storage while the full local footprint remains."
            )
        elif policy == "copy":
            object_tb = retained_copy_tb
            performance_tb = total_repo_tb
            rec = (
                f"Capacity Tier Copy: ~{object_tb:.1f} TB of retained/GFS backup data is modeled "
                "in object storage while the full local performance-tier footprint remains."
            )
        elif policy == "move":
            object_tb = moved_tb
            performance_tb = total_repo_tb - moved_tb
            rec = (
                f"Capacity Tier Move: ~{moved_tb:.1f} TB of sealed short-term backup data is "
                f"eligible to leave local storage after the {orw_days}-day operational restore "
                "window. GFS capacity remains local because GFS point ages are not explicit inputs."
            )
        else:
            object_tb = retained_copy_tb
            performance_tb = total_repo_tb - moved_tb
            rec = (
                f"Capacity Tier Copy + Move: ~{object_tb:.1f} TB of retained/GFS data is modeled "
                f"in object storage, while ~{moved_tb:.1f} TB of sealed short-term data is removed "
                f"from local storage after the {orw_days}-day operational restore window."
            )

        if reverse_move_uncredited:
            rec += (
                " Reverse-incremental local-capacity savings are not credited because this model "
                "does not define the periodic full event required to prove an inactive chain."
            )
        if forever_forward_gfs_uncredited:
            rec += (
                " GFS can create synthetic fulls that seal forever-forward chains, but the current "
                "GFS inputs are counts rather than dated schedules; no additional Move savings are "
                "credited without that age information."
            )

    performance_tb = max(0.0, performance_tb)
    extent_count, extent_size_tb = _extent_layout(performance_tb)

    if vin.capacity_tier_immutable and object_tb > 0:
        rec += " Object-lock immutability is enabled on the capacity tier."

    if vin.capacity_tier_enabled and repo.gfs_repo_tb > 0 and policy in {"move", "copy_move"}:
        rec += (
            " GFS Move savings are not deducted from local capacity because weekly/monthly/yearly "
            "point ages are not represented by the current input model."
        )

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
        operational_restore_window_days=orw_days if vin.capacity_tier_enabled else 0,
        move_eligible_short_term_tb=round(moved_tb, 1),
        move_model_basis=move_basis if vin.capacity_tier_enabled else "",
    )
