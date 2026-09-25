import pytest

from veeam_designer.models import VeeamInput
from veeam_designer.sizing import size_repository


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
