import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ui.main import app
from veeam_designer.service import (
    design_browser_bundle_from_project_text,
    design_payload_from_project_text,
)


def _vm_project(
    hypervisor: str,
    *,
    proxy_deployment_mode: str = "managed_os",
    on_host_proxy: bool = False,
    has_san_access: bool = False,
    platform_host_count: int = 4,
    platform_cluster_count: int = 1,
    platform_concurrent_tasks: int = 8,
    worker_task_limit: int = 4,
) -> str:
    return f"""workload_type: vm
total_data_tb: 100
annual_growth_percent: 10
daily_change_percent: 5
backup_type: synthetic_full_weekly
primary_retention_days: 30
gfs_weekly_count: 4
gfs_monthly_count: 12
gfs_yearly_count: 3
backup_window_hours: 8
target_rpo_hours: 24
vm_count: 200
avg_vm_size_gb: 512
repo_type: sobr
hypervisor: {hypervisor}
has_san_access: {str(has_san_access).lower()}
on_host_proxy: {str(on_host_proxy).lower()}
platform_host_count: {platform_host_count}
platform_cluster_count: {platform_cluster_count}
platform_concurrent_tasks: {platform_concurrent_tasks}
worker_task_limit: {worker_task_limit}
deployment_mode: software_appliance
proxy_deployment_mode: {proxy_deployment_mode}
concurrent_jobs: 20
"""


def test_legacy_v4_style_vm_project_still_designs():
    legacy = """workload_type: vm
total_data_tb: 50
daily_change_percent: 5
backup_window_hours: 8
vm_count: 100
hypervisor: vmware
repo_type: sobr
"""

    payload = design_payload_from_project_text(legacy, suffix=".yml")

    assert payload["kind"] == "vm"
    assert payload["roles"]["platform_workers"] is None
    assert payload["roles"]["proxies"]["proxy_count"] >= 2
    assert payload["roles"]["proxies"]["deployment_mode"] == "managed_os"
    assert payload["roles"]["backup_server"]["deployment_mode"] == "software_appliance"


def test_vmware_managed_and_infrastructure_appliance_keep_same_role_capacity():
    managed = design_payload_from_project_text(
        _vm_project("vmware", has_san_access=True),
        suffix=".yml",
    )
    appliance = design_payload_from_project_text(
        _vm_project(
            "vmware",
            has_san_access=True,
            proxy_deployment_mode="infrastructure_appliance",
        ),
        suffix=".yml",
    )

    managed_proxy = managed["roles"]["proxies"]
    appliance_proxy = appliance["roles"]["proxies"]

    assert appliance_proxy["proxy_count"] == managed_proxy["proxy_count"]
    assert appliance_proxy["cores_per_proxy"] == managed_proxy["cores_per_proxy"]
    assert appliance_proxy["estimated_capacity_mb_s"] == managed_proxy["estimated_capacity_mb_s"]
    assert appliance_proxy["allocated_cores_per_proxy"] == appliance_proxy["cores_per_proxy"] + 2
    assert appliance_proxy["allocated_ram_gb_per_proxy"] == appliance_proxy["ram_gb_per_proxy"] + 8
    assert appliance_proxy["infrastructure_system_disk_gb"] == 120
    assert appliance_proxy["infrastructure_data_disk_gb"] == 120


@pytest.mark.parametrize(
    ("hypervisor", "expected_platform"),
    [("proxmox", "proxmox"), ("ahv", "ahv")],
)
def test_worker_platforms_smoke_through_browser_bundle(hypervisor: str, expected_platform: str):
    bundle = design_browser_bundle_from_project_text(
        _vm_project(hypervisor),
        suffix=".yml",
    )
    payload = bundle["payload"]
    workers = payload["roles"]["platform_workers"]
    site = bundle["dashboard"]["sites"][0]

    assert workers["platform"] == expected_platform
    assert workers["worker_count"] >= 1
    assert workers["cores_per_worker"] >= 6
    assert workers["ram_gb_per_worker"] >= 6
    assert workers["disk_gb_per_worker"] == 100
    assert payload["roles"]["proxies"]["estimated_capacity_mb_s"] == 0.0
    assert site["platform_worker_count"] == workers["worker_count"]
    assert bundle["summary_cards"][1]["label"] == f"{expected_platform.upper()} Workers"
    assert "workers" in bundle["blueprint"].lower()
    assert bundle["csv"].startswith("field,value")


def test_hyperv_off_host_smoke_combines_throughput_and_task_model():
    payload = design_payload_from_project_text(
        _vm_project("hyperv", on_host_proxy=False, platform_concurrent_tasks=8),
        suffix=".yml",
    )
    proxy = payload["roles"]["proxies"]

    assert proxy["proxy_count"] == 2
    assert proxy["cores_per_proxy"] == 2
    assert proxy["ram_gb_per_proxy"] == 4
    assert proxy["total_parallel_tasks"] == 8
    assert proxy["transport_mode"] == "off-host"
    assert proxy["estimated_capacity_mb_s"] >= proxy["required_throughput_mb_s"]


def test_hyperv_on_host_smoke_accounts_for_each_supplied_host():
    payload = design_payload_from_project_text(
        _vm_project(
            "hyperv",
            on_host_proxy=True,
            platform_host_count=4,
            platform_concurrent_tasks=8,
        ),
        suffix=".yml",
    )
    proxy = payload["roles"]["proxies"]

    assert proxy["proxy_count"] == 4
    assert proxy["transport_mode"] == "on-host"
    assert proxy["total_parallel_tasks"] == 8


def test_hyperv_smoke_scales_with_change_rate_and_backup_window():
    normal = design_payload_from_project_text(
        _vm_project("hyperv", on_host_proxy=False),
        suffix=".yml",
    )

    pressured_project = _vm_project("hyperv", on_host_proxy=False)
    pressured_project = pressured_project.replace(
        "daily_change_percent: 5",
        "daily_change_percent: 20",
    ).replace(
        "backup_window_hours: 8",
        "backup_window_hours: 2",
    )
    pressured = design_payload_from_project_text(pressured_project, suffix=".yml")

    normal_proxy = normal["roles"]["proxies"]
    pressured_proxy = pressured["roles"]["proxies"]

    assert pressured_proxy["required_throughput_mb_s"] > normal_proxy["required_throughput_mb_s"]
    assert pressured_proxy["total_proxy_cores"] > normal_proxy["total_proxy_cores"]
    assert pressured_proxy["estimated_capacity_mb_s"] >= pressured_proxy["required_throughput_mb_s"]


@pytest.mark.parametrize("hypervisor", ["hyperv", "ahv", "proxmox", "mixed"])
def test_infrastructure_appliance_proxy_mode_rejects_non_vmware(hypervisor: str):
    with pytest.raises(ValueError, match="Infrastructure Appliance"):
        design_payload_from_project_text(
            _vm_project(hypervisor, proxy_deployment_mode="infrastructure_appliance"),
            suffix=".yml",
        )


def test_server_result_bundle_exposes_csv_and_stateless_report_is_inline():
    client = TestClient(app)
    project = _vm_project("vmware")

    page_response = client.post(
        "/run",
        data={"yaml_content": project, "run_blueprint": "1", "run_cost": "1"},
    )
    assert page_response.status_code == 200
    assert '"csv":' in page_response.text

    report_response = client.post(
        "/export/report",
        content=project,
        headers={"Content-Type": "text/plain"},
    )
    assert report_response.status_code == 200
    assert report_response.headers["content-type"].startswith("text/html")
    assert report_response.headers["content-disposition"].startswith("inline;")


def test_api_and_server_report_smoke_for_proxmox():
    client = TestClient(app)
    project = _vm_project("proxmox")

    api_response = client.post(
        "/api/design",
        content=project,
        headers={"Content-Type": "text/plain"},
    )
    assert api_response.status_code == 200
    api_payload = api_response.json()
    assert api_payload["roles"]["platform_workers"]["platform"] == "proxmox"

    page_response = client.post(
        "/run",
        data={"yaml_content": project, "run_blueprint": "1"},
    )
    assert page_response.status_code == 200
    assert "PROXMOX workers" in page_response.text

    report_response = client.post(
        "/export/report",
        content=project,
        headers={"Content-Type": "text/plain"},
    )
    assert report_response.status_code == 200
    assert "PROXMOX Workers" in report_response.text
    assert "Backup Server" in report_response.text
    assert "Retained short-term data" in report_response.text
    assert "Operational headroom" in report_response.text
    assert "Capacity basis" in report_response.text


def test_web_builder_exposes_hardened_calculation_inputs():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    for label in [
        "WAN Accelerator Mode",
        "Immutability Period",
        "Concurrent Sources",
        "Forecast Horizon",
        "Capacity Tier Offload",
        "Capacity Tier Object Lock",
        "Concurrent Proxy Tasks",
        "CDP Retention",
        "Measured CDP Write I/O",
    ]:
        assert label in response.text


def test_physical_presenter_uses_proxy_not_coordinator_language():
    bundle = design_browser_bundle_from_project_text(
        """workload_type: physical
machine_count: 20
avg_size_gb: 500
daily_change_pct: 5
retention_days: 14
backup_window_hours: 8
network_bandwidth_mbps: 1000
concurrent_tasks: 4
""",
        suffix=".yml",
    )

    labels = {card["label"] for card in bundle["summary_cards"]}
    assert "General Proxy" in labels
    assert "Coordinator Cores" not in labels
    assert "General-purpose proxy" in bundle["blueprint"]


def test_replication_presenter_exposes_cdp_retention_capacity():
    bundle = design_browser_bundle_from_project_text(
        """workload_type: replication
source_tb: 50
vm_count: 100
wan_mbps: 1000
daily_change_pct: 5
cdp_enabled: true
rpo_seconds: 15
cdp_retention_hours: 12
cdp_write_io_mb_s: 400
""",
        suffix=".yml",
    )

    labels = {card["label"] for card in bundle["summary_cards"]}
    assert "CDP Retention" in labels
    assert "CDP proxies per side" in bundle["blueprint"]


def test_checked_in_example_project_smoke():
    payload = design_payload_from_project_text(
        Path("example-project.yml").read_text(encoding="utf-8"),
        suffix=".yml",
    )

    assert payload["kind"] == "multi-site"
    assert len(payload["sites"]) == 2
    assert payload["sites"][0]["name"] == "Primary DC"
    assert payload["sites"][1]["name"] == "Recovery Site"
    assert (
        payload["sites"][0]["design"]["roles"]["backup_server"]["deployment_mode"]
        == "software_appliance"
    )


def test_cli_smoke_for_proxmox_json_output():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "veeam_designer.cli",
            "--total-data-tb",
            "25",
            "--daily-change-percent",
            "5",
            "--hypervisor",
            "proxmox",
            "--vm-count",
            "50",
            "--platform-host-count",
            "3",
            "--platform-concurrent-tasks",
            "4",
            "--worker-task-limit",
            "4",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["kind"] == "vm"
    assert payload["roles"]["platform_workers"]["platform"] == "proxmox"
    assert payload["roles"]["platform_workers"]["worker_count"] >= 1


@pytest.mark.parametrize(
    ("project", "expected_kind"),
    [
        (
            """workload_type: nas
source_tb: 10
share_count: 2
file_count_millions: 1
retention_days: 14
backup_window_hours: 8
""",
            "nas",
        ),
        (
            """workload_type: physical
machine_count: 10
avg_size_gb: 250
daily_change_pct: 5
retention_days: 14
backup_window_hours: 8
network_bandwidth_mbps: 1000
""",
            "physical",
        ),
        (
            """workload_type: replication
source_tb: 10
vm_count: 20
wan_mbps: 1000
daily_change_pct: 5
""",
            "replication",
        ),
    ],
)
def test_non_vm_browser_bundles_support_summary_csv_and_printable_content(project, expected_kind):
    bundle = design_browser_bundle_from_project_text(project, suffix=".yml")

    assert bundle["payload"]["kind"] == expected_kind
    assert bundle["summary_cards"]
    assert bundle["csv"].startswith("field,value")
    assert bundle["blueprint"]
