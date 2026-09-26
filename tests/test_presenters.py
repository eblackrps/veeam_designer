from veeam_designer import __version__
from veeam_designer.service import design_browser_bundle_from_project_text


def test_browser_bundle_contains_payload_and_exports():
    project_json = """
    {
      "profile": "enterprise",
      "workload_type": "replication",
      "source_tb": 100,
      "vm_count": 300,
      "wan_mbps": 1000,
      "rpo_hours": 1,
      "cdp_enabled": true
    }
    """

    bundle = design_browser_bundle_from_project_text(project_json)

    assert bundle["payload"]["kind"] == "replication"
    assert bundle["payload"]["version"] == __version__
    assert bundle["summary_cards"]
    assert "Replication sizing" in bundle["blueprint"]
    assert bundle["csv"].startswith("field,value")


def test_dashboard_uses_engine_reported_proxy_capacity():
    project_json = """
    {
      "profile": "enterprise",
      "workload_type": "vm",
      "total_data_tb": 500,
      "annual_growth_percent": 0,
      "daily_change_percent": 10,
      "backup_window_hours": 10,
      "on_host_proxy": true,
      "vm_count": 500
    }
    """

    bundle = design_browser_bundle_from_project_text(project_json)
    site = bundle["dashboard"]["sites"][0]
    roles = bundle["payload"]["roles"]["proxies"]

    assert site["proxy_capacity_mb_s"] == roles["estimated_capacity_mb_s"]
    assert site["proxy_throughput_basis"] == roles["throughput_basis"]


def test_dashboard_reports_platform_workers_for_proxmox():
    project_json = """
    {
      "profile": "enterprise",
      "workload_type": "vm",
      "total_data_tb": 100,
      "annual_growth_percent": 0,
      "daily_change_percent": 5,
      "backup_window_hours": 8,
      "hypervisor": "proxmox",
      "vm_count": 200,
      "platform_host_count": 4,
      "platform_cluster_count": 1,
      "platform_concurrent_tasks": 8,
      "worker_task_limit": 4,
      "deployment_mode": "software_appliance"
    }
    """

    bundle = design_browser_bundle_from_project_text(project_json)
    site = bundle["dashboard"]["sites"][0]

    assert site["platform_worker_platform"] == "proxmox"
    assert site["platform_worker_count"] == 2
    assert site["platform_worker_cores_each"] == 6
    assert site["platform_worker_ram_each"] == 6
    assert site["bs_deployment_mode"] == "software_appliance"
    assert "PROXMOX workers" in bundle["blueprint"]


def test_vm_summary_uses_total_storage_planning_cost_for_direct_object():
    project_json = """
    {
      "profile": "enterprise",
      "workload_type": "vm",
      "total_data_tb": 100,
      "annual_growth_percent": 0,
      "years_to_plan_for": 0,
      "daily_change_percent": 5,
      "backup_type": "forever_forward_incremental",
      "primary_retention_days": 7,
      "gfs_weekly_count": 0,
      "gfs_monthly_count": 0,
      "gfs_yearly_count": 0,
      "backup_window_hours": 8,
      "vm_count": 100,
      "repo_type": "object",
      "direct_to_object": true,
      "object_cost_usd_per_tb_month": 10,
      "onprem_cost_usd_per_tb_year": 999
    }
    """

    bundle = design_browser_bundle_from_project_text(project_json)
    cost = bundle["payload"]["cost"]
    summary = {card["label"]: card["value"] for card in bundle["summary_cards"]}

    assert cost["yearly_onprem_usd"] == 0.0
    assert cost["yearly_object_usd"] > 0.0
    assert cost["total_yearly_usd"] == cost["yearly_object_usd"]
    assert summary["Storage Planning/yr"] != "$0"

def test_vm_cost_summary_surfaces_object_lock_cost_guardrail():
    project_json = """
    {
      "profile": "enterprise",
      "workload_type": "vm",
      "total_data_tb": 100,
      "annual_growth_percent": 0,
      "years_to_plan_for": 0,
      "daily_change_percent": 5,
      "backup_type": "synthetic_full_weekly",
      "primary_retention_days": 7,
      "gfs_weekly_count": 0,
      "gfs_monthly_count": 0,
      "gfs_yearly_count": 0,
      "backup_window_hours": 8,
      "vm_count": 100,
      "repo_type": "sobr",
      "capacity_tier_enabled": true,
      "capacity_tier_policy": "copy",
      "capacity_tier_immutable": true,
      "object_cost_usd_per_tb_month": 20,
      "onprem_cost_usd_per_tb_year": 20
    }
    """

    bundle = design_browser_bundle_from_project_text(project_json)

    assert "base modeled footprint" in bundle["cost"]
    assert "Actual billed storage may be higher" in bundle["cost"]
    assert "Block Generation" in bundle["cost"]
