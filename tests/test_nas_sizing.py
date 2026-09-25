from veeam_designer.models import NasInput
from veeam_designer.nas import size_nas


def test_disk_target_capacity_uses_five_percent_metadata_and_workspace():
    result = size_nas(
        NasInput(
            source_tb=50.0,
            share_count=20,
            retention_days=14,
            concurrent_sources=1,
            object_storage=False,
        )
    )

    # 50 TB full + 35 TB incrementals = 85 TB.
    # Disk repository adds 5% metadata + 5% workspace.
    assert result.primary_repo_tb == 93.5
    assert result.cache_repo_tb == 0.0
    assert result.total_repo_tb == 93.5


def test_general_proxy_uses_bp_formula_with_current_system_minimums():
    result = size_nas(
        NasInput(
            source_tb=50.0,
            share_count=20,
            retention_days=14,
            concurrent_sources=1,
            object_storage=False,
        )
    )

    assert result.file_proxy_count == 2
    assert result.file_proxy_cores_each == 4
    assert result.file_proxy_ram_gb_each == 8
    assert result.file_proxy_cores == 8
    assert result.file_proxy_ram_gb == 16


def test_object_target_changes_cache_repository_compute_not_proxy_formula():
    disk = size_nas(
        NasInput(
            source_tb=50.0,
            share_count=20,
            concurrent_sources=1,
            object_storage=False,
        )
    )
    obj = size_nas(
        NasInput(
            source_tb=50.0,
            share_count=20,
            concurrent_sources=1,
            object_storage=True,
        )
    )

    assert obj.file_proxy_cores_each == disk.file_proxy_cores_each == 4
    assert obj.file_proxy_ram_gb_each == disk.file_proxy_ram_gb_each == 8

    assert disk.cache_repo_cores == 6
    assert disk.cache_repo_ram_gb == 8
    assert obj.cache_repo_cores == 8
    assert obj.cache_repo_ram_gb == 20


def test_proxy_and_cache_resources_scale_with_explicit_concurrent_sources():
    disk = size_nas(
        NasInput(
            source_tb=50.0,
            share_count=20,
            concurrent_sources=4,
            object_storage=False,
        )
    )
    obj = size_nas(
        NasInput(
            source_tb=50.0,
            share_count=20,
            concurrent_sources=4,
            object_storage=True,
        )
    )

    assert disk.file_proxy_cores_each == 4
    assert disk.file_proxy_ram_gb_each == 12
    assert disk.file_proxy_cores == 8
    assert disk.file_proxy_ram_gb == 24

    assert obj.file_proxy_cores_each == 4
    assert obj.file_proxy_ram_gb_each == 12

    assert disk.cache_repo_cores == 18
    assert disk.cache_repo_ram_gb == 20
    assert obj.cache_repo_cores == 26
    assert obj.cache_repo_ram_gb == 68


def test_object_cache_uses_one_gb_per_million_file_versions_minimum():
    result = size_nas(
        NasInput(
            source_tb=50.0,
            file_count_millions=5.5,
            object_storage=True,
        )
    )

    assert result.cache_repo_tb == 0.006
    assert any("6 GB" in note for note in result.notes)


def test_nas_with_gfs_does_not_add_separate_gfs_capacity():
    result = size_nas(
        NasInput(
            source_tb=50.0,
            gfs_weekly=4,
            gfs_monthly=12,
        )
    )

    assert result.gfs_repo_tb == 0.0
    assert any("incremental-forever" in note for note in result.notes)


def test_single_share_does_not_force_second_proxy():
    result = size_nas(
        NasInput(
            source_tb=10.0,
            share_count=1,
            concurrent_sources=1,
        )
    )

    assert result.file_proxy_count == 1
    assert result.file_proxy_cores_each == 4
    assert result.file_proxy_ram_gb_each == 10
