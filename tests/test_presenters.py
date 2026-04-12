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
