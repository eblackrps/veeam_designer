from veeam_designer import config as config_module


def test_packaged_config_used_when_repo_files_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "_project_root", lambda: tmp_path)

    base_config = config_module.load_base_config()
    profiles = config_module.load_profiles()

    assert base_config["throughput_mb_per_core"] == 15.0
    assert base_config["warn_repo_tb"] == 300.0
    assert "enterprise" in profiles
    assert profiles["dedupe"]["dedupe_ratio_default"] == 3.0
