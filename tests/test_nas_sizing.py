from veeam_designer.models import NasInput
from veeam_designer.nas import size_nas


def test_disk_target_uses_current_general_proxy_requirements():
    result = size_nas(
        NasInput(
            source_tb=50.0,
            share_count=20,
            retention_days=14,
            concurrent_sources=1,
            object_storage=False,
        )
    )

    assert result.total_repo_tb == 71.4
    assert result.cache_repo_tb == 0.0
    assert result.file_proxy_count == 2
    assert result.file_proxy_cores_each == 6
    assert result.file_proxy_ram_gb_each == 8
    assert result.file_proxy_cores == 12
    assert result.file_proxy_ram_gb == 16


def test_object_target_uses_stronger_proxy_requirements():
    result = size_nas(
        NasInput(
            source_tb=50.0,
            share_count=20,
            retention_days=14,
            concurrent_sources=1,
            object_storage=True,
        )
    )

    assert result.file_proxy_count == 2
    assert result.file_proxy_cores_each == 8
    assert result.file_proxy_ram_gb_each == 20
    assert result.file_proxy_cores == 16
    assert result.file_proxy_ram_gb == 40


def test_proxy_resources_scale_with_explicit_concurrent_sources():
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

    assert disk.file_proxy_cores_each == 10
    assert disk.file_proxy_ram_gb_each == 12
    assert disk.file_proxy_cores == 20
    assert disk.file_proxy_ram_gb == 24

    assert obj.file_proxy_cores_each == 14
    assert obj.file_proxy_ram_gb_each == 36
    assert obj.file_proxy_cores == 28
    assert obj.file_proxy_ram_gb == 72


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
    assert result.file_proxy_cores_each == 6
    assert result.file_proxy_ram_gb_each == 8
