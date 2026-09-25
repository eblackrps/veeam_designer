from veeam_designer import cost as cost_module
from veeam_designer.cost import estimate_costs
from veeam_designer.models import RepoSizing, SobrDesign, VeeamInput


def _repo(total_tb=100.0):
    return RepoSizing(
        primary_repo_tb=total_tb * 0.7,
        gfs_repo_tb=total_tb * 0.3,
        total_repo_tb=total_tb,
    )


def _sobr(cap_tb=0.0):
    return SobrDesign(
        extent_count=0,
        extent_size_tb=100.0 - cap_tb,
        capacity_tier_tb=cap_tb,
        archive_tier_tb=0.0,
        recommendation="test",
    )


def _vin(**kwargs):
    values = dict(
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
    values.update(kwargs)
    return VeeamInput(**values)


def test_default_install_does_not_invent_costs():
    result = estimate_costs(_repo(), _sobr(), _vin())

    assert result.configured is False
    assert result.monthly_object_usd == 0.0
    assert result.yearly_object_usd == 0.0
    assert result.yearly_onprem_usd == 0.0
    assert result.cloud_comparison == {}
    assert result.three_year_tco == {}
    assert result.break_even_years == 0.0


def test_explicit_rates_enable_cost_math(monkeypatch):
    monkeypatch.setattr(
        cost_module,
        "CONFIG",
        {
            "object_cost_usd_per_tb_month": 10.0,
            "onprem_cost_usd_per_tb_year": 100.0,
            "aws_s3_cost_per_tb_month": 0.0,
            "azure_blob_cost_per_tb_month": 0.0,
            "wasabi_cost_per_tb_month": 0.0,
            "objectfirst_cost_per_tb_month": 0.0,
        },
    )

    result = estimate_costs(
        _repo(100.0),
        _sobr(cap_tb=50.0),
        _vin(capacity_tier_enabled=True),
    )

    assert result.configured is True
    assert result.monthly_object_usd == 500.0
    assert result.yearly_object_usd == 6000.0
    assert result.yearly_onprem_usd == 5000.0
    assert result.three_year_tco["configured_design"] == 36410.0


def test_capacity_tier_without_fraction_does_not_assume_fifty_percent():
    result = estimate_costs(
        _repo(100.0),
        _sobr(cap_tb=0.0),
        _vin(capacity_tier_enabled=True, capacity_tier_fraction=0.0),
    )

    assert result.monthly_object_usd == 0.0
