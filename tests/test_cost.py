from veeam_designer.cost import estimate_costs
from veeam_designer.models import RepoSizing, SobrDesign, VeeamInput


def _repo(total_tb=100.0):
    return RepoSizing(
        primary_repo_tb=total_tb * 0.7, gfs_repo_tb=total_tb * 0.3, total_repo_tb=total_tb
    )


def _sobr(cap_tb=0.0):
    return SobrDesign(
        extent_count=1,
        extent_size_tb=100.0,
        capacity_tier_tb=cap_tb,
        archive_tier_tb=0.0,
        recommendation="ok",
    )


def _vin(**kwargs):
    d = dict(
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
    d.update(kwargs)
    return VeeamInput(**d)


def test_cost_has_values():
    c = estimate_costs(_repo(), _sobr(), _vin())
    assert c.yearly_onprem_usd > 0


def test_object_cost_with_capacity_tier():
    c = estimate_costs(_repo(), _sobr(cap_tb=50.0), _vin(capacity_tier_enabled=True))
    assert c.monthly_object_usd > 0


def test_cost_model_does_not_emit_fake_provider_or_break_even_precision():
    result = estimate_costs(_repo(), _sobr(cap_tb=50.0), _vin(capacity_tier_enabled=True))

    assert result.cloud_comparison == {}
    assert result.three_year_tco == {}
    assert result.break_even_years == 0.0
    assert any("planning rates only" in note for note in result.notes)


def test_direct_object_cost_assigns_capacity_to_object_not_onprem():
    result = estimate_costs(
        _repo(),
        _sobr(cap_tb=100.0),
        _vin(repo_type="object", direct_to_object=True),
    )

    assert result.yearly_onprem_usd == 0.0
    assert result.monthly_object_usd > 0.0
