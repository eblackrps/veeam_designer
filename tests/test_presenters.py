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
