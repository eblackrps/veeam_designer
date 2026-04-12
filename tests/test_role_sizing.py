from typing import Any, cast

from veeam_designer.models import ProxySizing, RepoSizing, VeeamInput
from veeam_designer.roles import size_backup_server, size_hardened_repo


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

    small = size_backup_server(proxies, _vm_input(workload_count=400, concurrent_jobs=40))
    medium = size_backup_server(proxies, _vm_input(workload_count=900, concurrent_jobs=80))
    large = size_backup_server(proxies, _vm_input(workload_count=4000, concurrent_jobs=400))

    assert (small.cores, small.ram_gb) == (12, 24)
    assert (medium.cores, medium.ram_gb) == (24, 32)
    assert (large.cores, large.ram_gb) == (48, 64)


def test_hardened_repo_host_compute_tracks_proxy_cores():
    repo = RepoSizing(primary_repo_tb=900.0, gfs_repo_tb=300.0, total_repo_tb=1200.0)

    result = size_hardened_repo(repo, proxy_total_cores=24, refs_xfs=True)

    assert result.count == 2
    assert result.tb_per_host == 600.0
    assert result.cpu_cores_each == 4
    assert result.ram_gb_each == 16
