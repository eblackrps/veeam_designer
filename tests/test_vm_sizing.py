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
    )
    defaults.update(kwargs)
    return VeeamInput(**defaults)


def test_forever_forward_uses_v13_n_plus_one_retention():
    result = size_repository(_base_input())

    # 100 TB full + seven 10 TB increments = 170 TB.
    assert result.primary_repo_tb == 170.0
    assert result.gfs_repo_tb == 0.0
    assert result.total_repo_tb == 170.0
    assert "8 total" in result.calculation_basis


def test_v13_minimum_three_restore_points_is_enforced():
    result = size_repository(_base_input(primary_retention_days=1))

    # Minimum three restore points: one full + two increments.
    assert result.primary_repo_tb == 120.0


def test_weekly_synthetic_without_fast_clone_accounts_for_chain_overlap():
    result = size_repository(
        _base_input(
            backup_type="synthetic_full_weekly",
            refs_xfs=False,
        )
    )

    # 8 desired restore points + up to 6 chain-boundary points = 14 points:
    # 2 fulls + 12 increments = 320 TB.
    assert result.primary_repo_tb == 320.0
    assert "14 restore points" in result.calculation_basis


def test_weekly_synthetic_with_fast_clone_does_not_duplicate_full_capacity():
    synthetic = size_repository(
        _base_input(
            backup_type="synthetic_full_weekly",
            refs_xfs=True,
        )
    )
    forever = size_repository(_base_input())

    assert synthetic.primary_repo_tb == forever.primary_repo_tb
    assert any("Fast Clone" in note for note in synthetic.notes)


def test_immutability_extends_retention_instead_of_adding_fake_percentage():
    base = size_repository(_base_input())
    immutable = size_repository(
        _base_input(
            immutability_enabled=True,
            immutability_days=14,
        )
    )

    # 14-day immutable window -> N+1 = 15 restore points:
    # 100 TB full + fourteen 10 TB increments = 240 TB.
    assert base.primary_repo_tb == 170.0
    assert immutable.primary_repo_tb == 240.0
    assert any("no arbitrary metadata percentage" in note for note in immutable.notes)


def test_gfs_is_conservative_full_equivalent_upper_bound():
    result = size_repository(
        _base_input(
            gfs_weekly_count=1,
            gfs_monthly_count=1,
        )
    )

    assert result.primary_repo_tb == 170.0
    assert result.gfs_repo_tb == 200.0
    assert result.total_repo_tb == 370.0
    assert any("full-equivalent upper bound" in note for note in result.notes)


def test_repo_grows_with_data():
    small = size_repository(_base_input(total_data_tb=50.0))
    large = size_repository(_base_input(total_data_tb=200.0))

    assert large.total_repo_tb > small.total_repo_tb


def test_repo_components_sum():
    result = size_repository(_base_input(gfs_weekly_count=1))

    assert result.total_repo_tb == result.primary_repo_tb + result.gfs_repo_tb
