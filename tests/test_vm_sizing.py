import pytest

from veeam_designer.models import VeeamInput
from veeam_designer.sizing import size_repository
from veeam_designer.sobr import design_sobr


def _base_input(**kwargs):
    defaults = dict(
        total_data_tb=100.0,
        annual_growth_percent=0.0,
        daily_change_percent=10.0,
        backup_type="forever_forward_incremental",
        primary_retention_days=7,
        gfs_weekly_count=0,
        gfs_monthly_count=0,
        gfs_yearly_count=0,
        backup_window_hours=8.0,
        target_rpo_hours=24.0,
        compression_ratio=1.0,
        dedupe_ratio=1.0,
        years_to_plan_for=0,
        refs_xfs=True,
        repo_type="sobr",
    )
    defaults.update(kwargs)
    return VeeamInput(**defaults)


def test_forever_forward_v13_n_plus_one_known_answer():
    result = size_repository(_base_input())

    assert result.short_term_data_tb == 170.0
    assert result.operational_headroom_tb == 125.0
    assert result.primary_repo_tb == 295.0
    assert result.total_repo_tb == 295.0
    assert "8 retained points" in result.calculation_basis


def test_v13_minimum_three_restore_points_known_answer():
    result = size_repository(_base_input(primary_retention_days=1))

    assert result.short_term_data_tb == 120.0
    assert result.primary_repo_tb == 245.0


def test_weekly_synthetic_without_fast_clone_chain_overlap_known_answer():
    result = size_repository(_base_input(backup_type="synthetic_full_weekly", refs_xfs=False))

    assert result.short_term_data_tb == 320.0
    assert result.operational_headroom_tb == 125.0
    assert result.primary_repo_tb == 445.0
    assert "14 restore points" in result.calculation_basis


def test_weekly_active_full_does_not_receive_fast_clone_capacity_savings():
    result = size_repository(_base_input(backup_type="active_full_weekly", refs_xfs=True))

    assert result.short_term_data_tb == 320.0
    assert result.primary_repo_tb == 445.0


def test_weekly_synthetic_fast_clone_uses_changed_block_model():
    result = size_repository(_base_input(backup_type="synthetic_full_weekly", refs_xfs=True))

    assert result.short_term_data_tb == 230.0
    assert result.operational_headroom_tb == 125.0
    assert result.primary_repo_tb == 355.0
    assert any("planning estimate" in note for note in result.notes)


def test_hardened_immutability_extends_retention_without_fake_percentage():
    result = size_repository(
        _base_input(
            backup_type="synthetic_full_weekly",
            immutability_enabled=True,
            immutability_days=14,
        )
    )

    assert result.short_term_data_tb == 300.0
    assert result.operational_headroom_tb == 125.0
    assert result.total_repo_tb == 425.0
    assert any("no arbitrary metadata percentage" in note for note in result.notes)


def test_immutability_without_duration_does_not_invent_capacity():
    base = size_repository(_base_input(backup_type="synthetic_full_weekly"))
    immutable = size_repository(
        _base_input(
            backup_type="synthetic_full_weekly",
            immutability_enabled=True,
            immutability_days=0,
        )
    )

    assert immutable.total_repo_tb == base.total_repo_tb
    assert any("no immutability duration" in note for note in immutable.notes)


@pytest.mark.parametrize("backup_type", ["forever_forward_incremental", "reverse_incremental"])
def test_hardened_immutability_rejects_unsupported_chain_types(backup_type):
    with pytest.raises(ValueError, match="hardened repositories"):
        size_repository(
            _base_input(
                backup_type=backup_type,
                immutability_enabled=True,
                immutability_days=14,
            )
        )


def test_gfs_is_conservative_full_equivalent_upper_bound():
    result = size_repository(_base_input(gfs_weekly_count=1, gfs_monthly_count=1))

    assert result.primary_repo_tb == 295.0
    assert result.gfs_repo_tb == 200.0
    assert result.total_repo_tb == 495.0
    assert any("full-equivalent upper bound" in note for note in result.notes)


def test_repo_components_sum_exactly_at_reported_precision():
    result = size_repository(_base_input(gfs_weekly_count=1))

    assert result.total_repo_tb == result.primary_repo_tb + result.gfs_repo_tb


def test_direct_object_uses_object_capacity_without_disk_headroom():
    vin = _base_input(
        backup_type="forever_forward_incremental",
        repo_type="sobr",
        direct_to_object=True,
    )

    repo = size_repository(vin)
    sobr = design_sobr(repo, vin)

    assert repo.short_term_data_tb == 170.0
    assert repo.operational_headroom_tb == 0.0
    assert repo.total_repo_tb == 170.0
    assert sobr.extent_count == 0
    assert sobr.capacity_tier_tb == 170.0
    assert sobr.performance_tier_tb == 0.0
    assert sobr.moved_to_capacity_tb == 170.0
    assert sobr.capacity_tier_policy == "direct"


@pytest.mark.parametrize("backup_type", ["reverse_incremental", "synthetic_full_weekly"])
def test_direct_object_rejects_unsupported_backup_chain_modes(backup_type):
    with pytest.raises(ValueError, match="object"):
        size_repository(
            _base_input(
                backup_type=backup_type,
                repo_type="object",
            )
        )


def test_capacity_tier_move_uses_operational_restore_window_known_answer():
    vin = _base_input(
        backup_type="synthetic_full_weekly",
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_operational_restore_days=7,
    )
    repo = size_repository(vin)
    sobr = design_sobr(repo, vin)

    assert repo.short_term_data_tb == 230.0
    assert repo.operational_headroom_tb == 125.0
    assert repo.total_repo_tb == 355.0
    assert sobr.operational_restore_window_days == 7
    assert sobr.move_eligible_short_term_tb == 60.0
    assert sobr.capacity_tier_tb == 60.0
    assert sobr.performance_tier_tb == 295.0
    assert sobr.moved_to_capacity_tb == 60.0
    assert sobr.capacity_tier_policy == "move"
    assert sobr.extent_count == 2
    assert sobr.extent_size_tb == 147.5
    assert "6 sealed restore point" in sobr.move_model_basis


def test_capacity_tier_zero_day_window_moves_all_sealed_fast_clone_changes():
    vin = _base_input(
        backup_type="synthetic_full_weekly",
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_operational_restore_days=0,
    )
    sobr = design_sobr(size_repository(vin), vin)

    assert sobr.capacity_tier_tb == 70.0
    assert sobr.performance_tier_tb == 285.0
    assert sobr.moved_to_capacity_tb == 70.0


def test_capacity_tier_long_window_keeps_all_short_term_data_local():
    vin = _base_input(
        backup_type="synthetic_full_weekly",
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_operational_restore_days=30,
    )
    sobr = design_sobr(size_repository(vin), vin)

    assert sobr.capacity_tier_tb == 0.0
    assert sobr.performance_tier_tb == 355.0
    assert sobr.moved_to_capacity_tb == 0.0
    assert "No sealed short-term restore point" in sobr.move_model_basis


def test_capacity_tier_active_full_moves_full_and_incremental_files_by_age():
    vin = _base_input(
        backup_type="active_full_weekly",
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_operational_restore_days=7,
    )
    repo = size_repository(vin)
    sobr = design_sobr(repo, vin)

    assert repo.short_term_data_tb == 320.0
    assert repo.total_repo_tb == 445.0
    assert sobr.capacity_tier_tb == 150.0
    assert sobr.performance_tier_tb == 295.0
    assert sobr.moved_to_capacity_tb == 150.0
    assert "1 full and 5 incremental" in sobr.move_model_basis


def test_capacity_tier_copy_keeps_full_local_footprint():
    vin = _base_input(
        backup_type="synthetic_full_weekly",
        capacity_tier_enabled=True,
        capacity_tier_policy="copy",
        capacity_tier_operational_restore_days=30,
    )
    repo = size_repository(vin)
    sobr = design_sobr(repo, vin)

    assert repo.total_repo_tb == 355.0
    assert sobr.capacity_tier_tb == 230.0
    assert sobr.performance_tier_tb == 355.0
    assert sobr.moved_to_capacity_tb == 0.0
    assert sobr.capacity_tier_policy == "copy"


def test_capacity_tier_copy_move_copies_all_and_uses_orw_for_local_aging():
    vin = _base_input(
        backup_type="synthetic_full_weekly",
        capacity_tier_enabled=True,
        capacity_tier_policy="copy_move",
        capacity_tier_operational_restore_days=7,
    )
    repo = size_repository(vin)
    sobr = design_sobr(repo, vin)

    assert repo.total_repo_tb == 355.0
    assert sobr.capacity_tier_tb == 230.0
    assert sobr.performance_tier_tb == 295.0
    assert sobr.moved_to_capacity_tb == 60.0
    assert sobr.capacity_tier_policy == "copy_move"


def test_legacy_capacity_fraction_no_longer_changes_move_sizing():
    low = _base_input(
        backup_type="synthetic_full_weekly",
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_fraction=0.0,
        capacity_tier_operational_restore_days=7,
    )
    high = _base_input(
        backup_type="synthetic_full_weekly",
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_fraction=1.0,
        capacity_tier_operational_restore_days=7,
    )

    low_sobr = design_sobr(size_repository(low), low)
    high_sobr = design_sobr(size_repository(high), high)

    assert low_sobr.capacity_tier_tb == 60.0
    assert high_sobr.capacity_tier_tb == 60.0
    assert low_sobr.performance_tier_tb == high_sobr.performance_tier_tb


def test_capacity_tier_move_keeps_gfs_local_without_dated_gfs_schedule():
    vin = _base_input(
        backup_type="synthetic_full_weekly",
        gfs_weekly_count=1,
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_operational_restore_days=7,
    )
    repo = size_repository(vin)
    sobr = design_sobr(repo, vin)

    assert repo.gfs_repo_tb == 100.0
    assert repo.total_repo_tb == 455.0
    assert sobr.capacity_tier_tb == 60.0
    assert sobr.performance_tier_tb == 395.0
    assert "GFS Move savings are not deducted" in sobr.recommendation


def test_capacity_tier_rejects_unknown_policy():
    vin = _base_input(
        backup_type="synthetic_full_weekly",
        capacity_tier_enabled=True,
        capacity_tier_policy="magic",
    )

    with pytest.raises(ValueError, match="capacity_tier_policy"):
        design_sobr(size_repository(vin), vin)


def test_forever_forward_capacity_tier_move_is_modeled_as_copy_without_gfs():
    vin = _base_input(
        backup_type="forever_forward_incremental",
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_operational_restore_days=7,
    )
    repo = size_repository(vin)
    sobr = design_sobr(repo, vin)

    assert repo.total_repo_tb == 295.0
    assert sobr.capacity_tier_policy == "copy"
    assert sobr.capacity_tier_tb == 170.0
    assert sobr.performance_tier_tb == 295.0
    assert sobr.moved_to_capacity_tb == 0.0
    assert "Move is ignored" in sobr.recommendation


def test_forever_forward_gfs_move_does_not_invent_gfs_age_savings():
    vin = _base_input(
        backup_type="forever_forward_incremental",
        gfs_weekly_count=1,
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_operational_restore_days=7,
    )
    repo = size_repository(vin)
    sobr = design_sobr(repo, vin)

    assert repo.total_repo_tb == 395.0
    assert sobr.capacity_tier_policy == "move"
    assert sobr.capacity_tier_tb == 0.0
    assert sobr.performance_tier_tb == 395.0
    assert "GFS can create synthetic fulls" in sobr.recommendation
