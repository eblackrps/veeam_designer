from veeam_designer.cost import estimate_costs
from veeam_designer.models import RepoSizing, SobrDesign, VeeamInput


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


def test_capacity_tier_object_lock_marks_cost_as_base_footprint():
    result = estimate_costs(
        _repo(),
        _sobr(capacity_tb=100.0, performance_tb=100.0, policy="copy"),
        _vin(
            capacity_tier_enabled=True,
            capacity_tier_policy="copy",
            capacity_tier_immutable=True,
        ),
    )

    assert result.total_yearly_usd == 26000.0
    assert any("base footprint estimate" in note for note in result.notes)
    assert any("actual object storage cost can be higher" in note for note in result.notes)
