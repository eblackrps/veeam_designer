from veeam_designer.cost import estimate_costs
from veeam_designer.models import RepoSizing, SobrDesign, VeeamInput
from veeam_designer.sizing import size_repository
from veeam_designer.sobr import design_sobr


def _repo(total_tb=100.0):
    return RepoSizing(
        primary_repo_tb=70.0,
        gfs_repo_tb=30.0,
        total_repo_tb=total_tb,
        short_term_data_tb=70.0,
        operational_headroom_tb=0.0,
    )


def _sobr(
    *,
    capacity_tb=0.0,
    performance_tb=100.0,
    moved_tb=0.0,
    policy="none",
):
    return SobrDesign(
        extent_count=1 if performance_tb else 0,
        extent_size_tb=performance_tb,
        capacity_tier_tb=capacity_tb,
        archive_tier_tb=0.0,
        recommendation="test",
        performance_tier_tb=performance_tb,
        moved_to_capacity_tb=moved_tb,
        capacity_tier_policy=policy,
    )


def _vin(**kwargs):
    defaults = dict(
        total_data_tb=100.0,
        annual_growth_percent=0.0,
        daily_change_percent=5.0,
        backup_type="synthetic_full_weekly",
        primary_retention_days=30,
        gfs_weekly_count=0,
        gfs_monthly_count=0,
        gfs_yearly_count=0,
        backup_window_hours=8.0,
        target_rpo_hours=24.0,
        object_cost_usd_per_tb_month=20.0,
        onprem_cost_usd_per_tb_year=20.0,
    )
    defaults.update(kwargs)
    return VeeamInput(**defaults)


def test_local_only_storage_cost_known_answer():
    result = estimate_costs(_repo(), _sobr(), _vin())

    assert result.monthly_object_usd == 0.0
    assert result.yearly_object_usd == 0.0
    assert result.yearly_onprem_usd == 2000.0
    assert result.total_yearly_usd == 2000.0


def test_capacity_tier_move_cost_known_answer():
    result = estimate_costs(
        _repo(),
        _sobr(capacity_tb=50.0, performance_tb=50.0, moved_tb=50.0, policy="move"),
        _vin(capacity_tier_enabled=True, capacity_tier_policy="move"),
    )

    assert result.monthly_object_usd == 1000.0
    assert result.yearly_object_usd == 12000.0
    assert result.yearly_onprem_usd == 1000.0
    assert result.total_yearly_usd == 13000.0


def test_capacity_tier_copy_is_additive_known_answer():
    result = estimate_costs(
        _repo(),
        _sobr(capacity_tb=100.0, performance_tb=100.0, policy="copy"),
        _vin(capacity_tier_enabled=True, capacity_tier_policy="copy"),
    )

    assert result.monthly_object_usd == 2000.0
    assert result.yearly_object_usd == 24000.0
    assert result.yearly_onprem_usd == 2000.0
    assert result.total_yearly_usd == 26000.0
    assert any("Copy is additive" in note for note in result.notes)


def test_capacity_tier_copy_move_combines_full_copy_with_local_aging():
    result = estimate_costs(
        _repo(),
        _sobr(
            capacity_tb=100.0,
            performance_tb=50.0,
            moved_tb=50.0,
            policy="copy_move",
        ),
        _vin(capacity_tier_enabled=True, capacity_tier_policy="copy_move"),
    )

    assert result.monthly_object_usd == 2000.0
    assert result.yearly_object_usd == 24000.0
    assert result.yearly_onprem_usd == 1000.0
    assert result.total_yearly_usd == 25000.0


def test_direct_object_cost_known_answer():
    result = estimate_costs(
        _repo(),
        _sobr(capacity_tb=100.0, performance_tb=0.0, moved_tb=100.0, policy="direct"),
        _vin(repo_type="object", direct_to_object=True),
    )

    assert result.monthly_object_usd == 2000.0
    assert result.yearly_object_usd == 24000.0
    assert result.yearly_onprem_usd == 0.0
    assert result.total_yearly_usd == 24000.0


def test_explicit_rates_drive_cost_exactly():
    result = estimate_costs(
        _repo(),
        _sobr(capacity_tb=25.0, performance_tb=75.0, moved_tb=25.0, policy="move"),
        _vin(
            capacity_tier_enabled=True,
            capacity_tier_policy="move",
            object_cost_usd_per_tb_month=10.0,
            onprem_cost_usd_per_tb_year=100.0,
        ),
    )

    assert result.yearly_object_usd == 3000.0
    assert result.yearly_onprem_usd == 7500.0
    assert result.total_yearly_usd == 10500.0


def test_cost_model_does_not_emit_fake_provider_or_break_even_precision():
    result = estimate_costs(_repo(), _sobr(), _vin())

    assert result.cloud_comparison == {}
    assert result.three_year_tco == {}
    assert result.break_even_years == 0.0
    assert any("not live" in note for note in result.notes)
    assert any("retrieval/egress" in note for note in result.notes)


def test_orw_driven_move_cost_known_answer_end_to_end():
    vin = _vin(
        daily_change_percent=10.0,
        backup_type="synthetic_full_weekly",
        primary_retention_days=7,
        gfs_weekly_count=0,
        gfs_monthly_count=0,
        gfs_yearly_count=0,
        compression_ratio=1.0,
        dedupe_ratio=1.0,
        years_to_plan_for=0,
        refs_xfs=True,
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_operational_restore_days=7,
    )
    repo = size_repository(vin)
    sobr = design_sobr(repo, vin)
    result = estimate_costs(repo, sobr, vin)

    assert sobr.capacity_tier_tb == 60.0
    assert sobr.performance_tier_tb == 295.0
    assert result.monthly_object_usd == 1200.0
    assert result.yearly_object_usd == 14400.0
    assert result.yearly_onprem_usd == 5900.0
    assert result.total_yearly_usd == 20300.0


def test_orw_changes_cost_without_any_move_fraction_input():
    seven_day = _vin(
        daily_change_percent=10.0,
        backup_type="synthetic_full_weekly",
        primary_retention_days=7,
        gfs_weekly_count=0,
        gfs_monthly_count=0,
        gfs_yearly_count=0,
        compression_ratio=1.0,
        dedupe_ratio=1.0,
        years_to_plan_for=0,
        refs_xfs=True,
        capacity_tier_enabled=True,
        capacity_tier_policy="move",
        capacity_tier_operational_restore_days=7,
    )
    zero_day = VeeamInput(
        **{
            **seven_day.__dict__,
            "capacity_tier_operational_restore_days": 0,
            "capacity_tier_fraction": 0.0,
        }
    )

    seven_cost = estimate_costs(
        size_repository(seven_day),
        design_sobr(size_repository(seven_day), seven_day),
        seven_day,
    )
    zero_repo = size_repository(zero_day)
    zero_cost = estimate_costs(zero_repo, design_sobr(zero_repo, zero_day), zero_day)

    assert seven_cost.total_yearly_usd == 20300.0
    assert zero_cost.total_yearly_usd == 22500.0
