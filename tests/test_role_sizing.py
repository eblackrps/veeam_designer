from typing import Any, cast

import pytest

from veeam_designer.models import ProxySizing, RepoSizing, VeeamInput
from veeam_designer.platforms import size_platform_workers
from veeam_designer.roles import size_backup_server, size_hardened_repo, size_proxies
from veeam_designer.service import design_payload_from_project_text


def _vm_input(**overrides) -> VeeamInput:
    defaults = dict(
        total_data_tb=100.0,
        annual_growth_percent=0.0,
        daily_change_percent=5.0,
        backup_type="synthetic_full_weekly",
        primary_retention_days=30,
        gfs_weekly_count=4,
        gfs_monthly_count=12,
        gfs_yearly_count=3,
        backup_window_hours=8.0,
        target_rpo_hours=24.0,
        vm_count=400,
        workload_count=400,
    )
    defaults.update(overrides)
    return VeeamInput(**cast(dict[str, Any], defaults))


def test_backup_server_uses_published_workload_bands():
    proxies = ProxySizing(
        proxy_count=2,
        cores_per_proxy=4,
        total_proxy_cores=8,
        total_parallel_tasks=16,
        required_throughput_mb_s=100.0,
    )

    small = size_backup_server(
        proxies, _vm_input(workload_count=400, concurrent_jobs=10, deployment_mode="windows")
    )
    medium = size_backup_server(
        proxies, _vm_input(workload_count=900, concurrent_jobs=20, deployment_mode="windows")
    )
    large = size_backup_server(
        proxies, _vm_input(workload_count=4000, concurrent_jobs=40, deployment_mode="windows")
    )

    assert (small.cores, small.ram_gb) == (12, 24)
    assert (medium.cores, medium.ram_gb) == (24, 32)
    assert (large.cores, large.ram_gb) == (48, 64)


def test_software_appliance_enforces_ram_per_concurrent_job():
    proxies = ProxySizing(
        proxy_count=2,
        cores_per_proxy=4,
        total_proxy_cores=8,
        total_parallel_tasks=16,
        required_throughput_mb_s=100.0,
    )

    result = size_backup_server(
        proxies,
        _vm_input(workload_count=400, concurrent_jobs=40, deployment_mode="software_appliance"),
    )

    assert result.cores == 12
    assert result.ram_gb == 36
    assert result.system_disk_gb == 240
    assert result.secondary_disk_gb == 240
    assert result.deployment_mode == "software_appliance"


def test_windows_backup_server_enforces_current_concurrency_memory_minimum():
    proxies = ProxySizing(
        proxy_count=2,
        cores_per_proxy=4,
        total_proxy_cores=8,
        total_parallel_tasks=16,
        required_throughput_mb_s=100.0,
    )

    result = size_backup_server(
        proxies,
        _vm_input(workload_count=900, concurrent_jobs=80, deployment_mode="windows"),
    )

    assert (result.cores, result.ram_gb) == (24, 56)
    assert result.system_disk_gb == 0
    assert result.secondary_disk_gb == 0
    assert result.deployment_mode == "windows"


def test_hardened_repo_host_compute_tracks_proxy_cores():
    repo = RepoSizing(primary_repo_tb=900.0, gfs_repo_tb=300.0, total_repo_tb=1200.0)

    result = size_hardened_repo(repo, proxy_total_cores=24, refs_xfs=True)

    assert result.count == 2
    assert result.tb_per_host == 600.0
    assert result.cpu_cores_each == 4
    assert result.ram_gb_each == 16


def test_proxmox_workers_use_vendor_task_model():
    result = size_platform_workers(
        _vm_input(
            hypervisor="proxmox",
            platform_concurrent_tasks=8,
            worker_task_limit=4,
            platform_cluster_count=1,
        )
    )

    assert result is not None
    assert result.platform == "proxmox"
    assert result.worker_count == 2
    assert result.cores_per_worker == 6
    assert result.ram_gb_per_worker == 6
    assert result.disk_gb_per_worker == 100
    assert result.total_concurrent_tasks == 8


def test_ahv_worker_resources_scale_above_four_tasks():
    result = size_platform_workers(
        _vm_input(
            hypervisor="ahv",
            platform_concurrent_tasks=6,
            worker_task_limit=6,
            platform_cluster_count=1,
            platform_host_count=4,
        )
    )

    assert result is not None
    assert result.worker_count == 1
    assert result.cores_per_worker == 8
    assert result.ram_gb_per_worker == 8
    assert result.total_concurrent_tasks == 6


def test_platform_workers_are_exposed_in_api_payload():
    payload = design_payload_from_project_text(
        """workload_type: vm
total_data_tb: 50
daily_change_percent: 5
backup_window_hours: 8
hypervisor: proxmox
vm_count: 120
platform_host_count: 3
platform_cluster_count: 1
platform_concurrent_tasks: 8
worker_task_limit: 4
deployment_mode: software_appliance
""",
        suffix=".yml",
    )

    workers = payload["roles"]["platform_workers"]
    assert workers["platform"] == "proxmox"
    assert workers["worker_count"] == 2
    assert payload["roles"]["backup_server"]["deployment_mode"] == "software_appliance"
    assert payload["roles"]["backup_server"]["system_disk_gb"] == 240
    assert payload["roles"]["backup_server"]["secondary_disk_gb"] == 240


def test_hyperv_uses_throughput_method_plus_native_task_resources():
    result = size_proxies(
        _vm_input(
            hypervisor="hyperv",
            on_host_proxy=False,
            platform_concurrent_tasks=8,
            worker_task_limit=4,
        )
    )

    assert result.proxy_count == 2
    assert result.cores_per_proxy == 2
    assert result.ram_gb_per_proxy == 4
    assert result.disk_gb_per_proxy == 0.3
    assert result.total_parallel_tasks == 8
    assert result.estimated_capacity_mb_s >= result.required_throughput_mb_s
    assert "Hyper-V BP uses vSphere proxy sizing method" in result.throughput_basis
    assert "hyperv_proxies.html" in result.source_url


def test_hyperv_short_window_scales_proxy_compute_from_throughput():
    baseline = size_proxies(
        _vm_input(
            hypervisor="hyperv",
            on_host_proxy=False,
            platform_concurrent_tasks=8,
            worker_task_limit=4,
            daily_change_percent=5.0,
            backup_window_hours=8.0,
        )
    )
    pressured = size_proxies(
        _vm_input(
            hypervisor="hyperv",
            on_host_proxy=False,
            platform_concurrent_tasks=8,
            worker_task_limit=4,
            daily_change_percent=20.0,
            backup_window_hours=2.0,
        )
    )

    assert pressured.required_throughput_mb_s > baseline.required_throughput_mb_s
    assert pressured.total_proxy_cores > baseline.total_proxy_cores
    assert pressured.estimated_capacity_mb_s >= pressured.required_throughput_mb_s


def test_hyperv_on_host_mode_accounts_for_supplied_hosts():
    result = size_proxies(
        _vm_input(
            hypervisor="hyper-v",
            on_host_proxy=True,
            platform_host_count=4,
            platform_concurrent_tasks=8,
            worker_task_limit=4,
        )
    )

    assert result.proxy_count == 4
    assert result.transport_mode == "on-host"
    assert result.total_parallel_tasks == 8
    assert any("On-host mode" in note for note in result.notes)


def test_vmware_infrastructure_appliance_adds_overhead_without_inflating_throughput():
    managed = size_proxies(
        _vm_input(
            hypervisor="vmware",
            on_host_proxy=False,
            has_san_access=True,
            proxy_deployment_mode="managed_os",
        )
    )
    appliance = size_proxies(
        _vm_input(
            hypervisor="vmware",
            on_host_proxy=False,
            has_san_access=True,
            proxy_deployment_mode="infrastructure_appliance",
        )
    )

    assert appliance.proxy_count == managed.proxy_count
    assert appliance.cores_per_proxy == managed.cores_per_proxy
    assert appliance.estimated_capacity_mb_s == managed.estimated_capacity_mb_s
    assert appliance.allocated_cores_per_proxy == appliance.cores_per_proxy + 2
    assert appliance.allocated_ram_gb_per_proxy == appliance.ram_gb_per_proxy + 8
    assert appliance.infrastructure_system_disk_gb == 120
    assert appliance.infrastructure_data_disk_gb == 120
    assert appliance.deployment_mode == "infrastructure_appliance"


def test_infrastructure_appliance_proxy_mode_is_rejected_for_non_vmware_platforms():
    with pytest.raises(ValueError, match="Infrastructure Appliance"):
        size_proxies(
            _vm_input(
                hypervisor="hyperv",
                proxy_deployment_mode="infrastructure_appliance",
            )
        )


def test_direct_object_role_plan_does_not_invent_disk_repo_or_gateway_roles():
    payload = design_payload_from_project_text(
        """workload_type: vm
total_data_tb: 50
daily_change_percent: 5
backup_type: forever_forward_incremental
primary_retention_days: 14
backup_window_hours: 8
vm_count: 100
avg_vm_size_gb: 512
repo_type: sobr
direct_to_object: true
immutability_enabled: false
hypervisor: vmware
""",
        suffix=".yml",
    )

    assert payload["roles"]["hardened_repos"] is None
    assert payload["roles"]["gateways"] is None
    assert all(job["repo_target"] == "object" for job in payload["jobs"])
    assert payload["risk"]["details"]["immutability"] == 1
    assert "Vendor appliance node count is not inferred" in payload["notes"]["object_storage"]
