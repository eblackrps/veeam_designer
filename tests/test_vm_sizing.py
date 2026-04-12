from veeam_designer.models import VeeamInput
from veeam_designer.sizing import size_repository


def _base_input(**kwargs):
    defaults = dict(
        total_data_tb=100.0,
        annual_growth_percent=10.0,
        daily_change_percent=5.0,
        backup_type="synthetic_full_weekly",
        primary_retention_days=30,
        gfs_weekly_count=4,
        gfs_monthly_count=12,
        gfs_yearly_count=3,
        backup_window_hours=8.0,
        target_rpo_hours=24.0,
    )
    defaults.update(kwargs)
    return VeeamInput(**defaults)


def test_repo_grows_with_data():
    small = size_repository(_base_input(total_data_tb=50.0))
    large = size_repository(_base_input(total_data_tb=200.0))
    assert large.total_repo_tb > small.total_repo_tb


def test_gfs_adds_to_total():
    no_gfs = size_repository(
        _base_input(gfs_weekly_count=0, gfs_monthly_count=0, gfs_yearly_count=0)
    )
    with_gfs = size_repository(_base_input())
    assert with_gfs.total_repo_tb > no_gfs.total_repo_tb


def test_immutability_overhead():
    base = size_repository(_base_input())
    immut = size_repository(_base_input(immutability_enabled=True))
    assert immut.total_repo_tb > base.total_repo_tb


def test_repo_components_sum():
    r = size_repository(_base_input())
    assert abs(r.total_repo_tb - (r.primary_repo_tb + r.gfs_repo_tb)) < 2.0
