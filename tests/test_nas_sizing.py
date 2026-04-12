from veeam_designer.models import NasInput
from veeam_designer.nas import size_nas


def test_nas_basic():
    nin = NasInput(source_tb=50.0, share_count=20, retention_days=14)
    r = size_nas(nin)
    assert r.total_repo_tb > 0
    assert r.file_proxy_cores >= 1


def test_nas_with_gfs():
    nin = NasInput(source_tb=50.0, gfs_weekly=4, gfs_monthly=12)
    r = size_nas(nin)
    assert r.gfs_repo_tb == 0.0
    assert any("incremental-forever" in note for note in r.notes)


def test_nas_object_storage_flag():
    nin = NasInput(source_tb=50.0, object_storage=True)
    r = size_nas(nin)
    assert r.total_repo_tb > 0
    assert r.cache_repo_tb == 2.5


def test_nas_disk_target_has_no_separate_cache_repo():
    nin = NasInput(source_tb=50.0, object_storage=False)
    r = size_nas(nin)
    assert r.cache_repo_tb == 0.0
    assert any("cache-repository disk usage is usually small" in note for note in r.notes)
