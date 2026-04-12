import json
from contextvars import copy_context

from veeam_designer.config import BASE_CONFIG, CONFIG, select_profile
from veeam_designer.jobs import build_jobs
from veeam_designer.models import ReplicationInput, VeeamInput
from veeam_designer.network import build_network_plan
from veeam_designer.parser import load_project_text
from veeam_designer.replication import size_replication
from veeam_designer.repo_perf import estimate_repo_perf
from veeam_designer.roles import size_proxies
from veeam_designer.service import design_payload_from_project_text
from veeam_designer.sizing import size_repository


def _vm_input(**overrides) -> VeeamInput:
    total_data_tb = overrides.pop("total_data_tb", 100.0)
    annual_growth_percent = overrides.pop("annual_growth_percent", 50.0)
    daily_change_percent = overrides.pop("daily_change_percent", 10.0)
    backup_type = overrides.pop("backup_type", "synthetic_full_weekly")
    primary_retention_days = overrides.pop("primary_retention_days", 7)
    gfs_weekly_count = overrides.pop("gfs_weekly_count", 0)
    gfs_monthly_count = overrides.pop("gfs_monthly_count", 0)
    gfs_yearly_count = overrides.pop("gfs_yearly_count", 0)
    backup_window_hours = overrides.pop("backup_window_hours", 10.0)
    target_rpo_hours = overrides.pop("target_rpo_hours", 24.0)
    compression_ratio = overrides.pop("compression_ratio", 1.0)
    dedupe_ratio = overrides.pop("dedupe_ratio", 1.0)
    read_write_overhead = overrides.pop("read_write_overhead", 1.0)
    years_to_plan_for = overrides.pop("years_to_plan_for", 2)
    wan_bandwidth_mbps = overrides.pop("wan_bandwidth_mbps", 5000.0)
    on_host_proxy = overrides.pop("on_host_proxy", True)
    return VeeamInput(
        total_data_tb=total_data_tb,
        annual_growth_percent=annual_growth_percent,
        daily_change_percent=daily_change_percent,
        backup_type=backup_type,
        primary_retention_days=primary_retention_days,
        gfs_weekly_count=gfs_weekly_count,
        gfs_monthly_count=gfs_monthly_count,
        gfs_yearly_count=gfs_yearly_count,
        backup_window_hours=backup_window_hours,
        target_rpo_hours=target_rpo_hours,
        compression_ratio=compression_ratio,
        dedupe_ratio=dedupe_ratio,
        read_write_overhead=read_write_overhead,
        years_to_plan_for=years_to_plan_for,
        wan_bandwidth_mbps=wan_bandwidth_mbps,
        on_host_proxy=on_host_proxy,
        **overrides,
    )


def test_repository_growth_math_uses_projected_change_rate():
    repo = size_repository(_vm_input())

    assert repo.primary_repo_tb == 400.0
    assert repo.gfs_repo_tb == 0.0
    assert repo.total_repo_tb == 400.0


def test_vm_runtime_components_stay_consistent_with_growth_horizon():
    vin = _vm_input()

    proxies = size_proxies(vin)
    repo_perf = estimate_repo_perf(vin, size_repository(vin), build_jobs(vin))
    network = build_network_plan(vin, size_repository(vin))

    assert proxies.proxy_count == 2
    assert proxies.required_throughput_mb_s == 582.5
    assert proxies.estimated_capacity_mb_s == 640.0
    assert repo_perf.required_mb_s == 582.5
    assert repo_perf.synthetic_full_mb_s == 582.5
    assert network.required_mbps == 4660.3
    assert network.meets_target is True


def test_project_payload_honors_years_to_plan_and_read_write_overhead():
    project_text = json.dumps(
        {
            "workload_type": "vm",
            "total_data_tb": 100.0,
            "annual_growth_percent": 50.0,
            "daily_change_percent": 10.0,
            "backup_type": "synthetic_full_weekly",
            "primary_retention_days": 7,
            "gfs_weekly_count": 0,
            "gfs_monthly_count": 0,
            "gfs_yearly_count": 0,
            "backup_window_hours": 10.0,
            "target_rpo_hours": 24.0,
            "compression_ratio": 1.0,
            "dedupe_ratio": 1.0,
            "read_write_overhead": 1.0,
            "years_to_plan_for": 2,
            "wan_bandwidth_mbps": 5000.0,
            "on_host_proxy": True,
        }
    )

    payload = design_payload_from_project_text(project_text, suffix=".json")

    assert payload["kind"] == "vm"
    assert payload["input"]["years_to_plan_for"] == 2
    assert payload["input"]["read_write_overhead"] == 1.0
    assert payload["repo"]["total_repo_tb"] == 400.0
    assert payload["roles"]["proxies"]["proxy_count"] == 2
    assert payload["repo_perf"]["required_mb_s"] == 582.5
    assert payload["wan_accel"]["source_digest_gb_per_source"] == 4000
    assert payload["wan_accel"]["target_total_free_space_gb"] == 5000


def test_replication_project_honors_daily_change_percent():
    low_change = load_project_text(
        json.dumps(
            {
                "workload_type": "replication",
                "source_tb": 100.0,
                "vm_count": 50,
                "wan_mbps": 2000.0,
                "daily_change_pct": 5.0,
            }
        ),
        suffix=".json",
    )
    high_change = load_project_text(
        json.dumps(
            {
                "workload_type": "replication",
                "source_tb": 100.0,
                "vm_count": 50,
                "wan_mbps": 2000.0,
                "daily_change_pct": 20.0,
            }
        ),
        suffix=".json",
    )

    assert isinstance(low_change, ReplicationInput)
    assert isinstance(high_change, ReplicationInput)
    low_result = size_replication(low_change)
    high_result = size_replication(high_change)

    assert low_change.daily_change_pct == 5.0
    assert high_change.daily_change_pct == 20.0
    assert low_result.required_mbps == 485.5
    assert high_result.required_mbps == 1941.8


def test_projects_without_profile_reset_to_base_configuration():
    select_profile(None)
    assert CONFIG["warn_repo_tb"] == BASE_CONFIG["warn_repo_tb"]

    load_project_text(
        json.dumps(
            {
                "profile": "enterprise",
                "workload_type": "vm",
                "total_data_tb": 10.0,
                "daily_change_percent": 5.0,
                "backup_window_hours": 8.0,
            }
        ),
        suffix=".json",
    )
    assert CONFIG["warn_repo_tb"] == 500.0

    load_project_text(
        json.dumps(
            {
                "workload_type": "vm",
                "total_data_tb": 10.0,
                "daily_change_percent": 5.0,
                "backup_window_hours": 8.0,
            }
        ),
        suffix=".json",
    )
    assert CONFIG["warn_repo_tb"] == BASE_CONFIG["warn_repo_tb"]


def test_profile_selection_is_context_local():
    select_profile(None)

    def warn_tb_for(profile_name: str | None) -> float:
        select_profile(profile_name)
        return float(CONFIG["warn_repo_tb"])

    enterprise_warn = copy_context().run(warn_tb_for, "enterprise")
    smb_warn = copy_context().run(warn_tb_for, "smb")

    assert enterprise_warn == 500.0
    assert smb_warn == 200.0
    assert float(CONFIG["warn_repo_tb"]) == float(BASE_CONFIG["warn_repo_tb"])


def test_custom_proxy_throughput_override_is_explicit():
    vin = _vm_input(
        total_data_tb=500.0,
        annual_growth_percent=0.0,
        daily_change_percent=10.0,
        years_to_plan_for=0,
        throughput_mb_per_core=200.0,
    )

    proxies = size_proxies(vin)

    assert proxies.total_proxy_cores == 8
    assert proxies.estimated_capacity_mb_s == 1600.0
    assert proxies.throughput_basis == "custom benchmark override"
