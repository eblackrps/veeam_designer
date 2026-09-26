from veeam_designer import config as config_module


def test_packaged_config_used_when_repo_files_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "_project_root", lambda: tmp_path)

    base_config = config_module.load_base_config()
    profiles = config_module.load_profiles()

    assert base_config["warn_repo_tb"] == 300.0
    assert "enterprise" in profiles
    assert profiles["dedupe"]["dedupe_ratio_default"] == 3.0
    assert "throughput_mb_per_core" not in profiles["smb"]


def test_packaged_config_has_no_stale_fake_pricing_or_gfs_knobs(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "_project_root", lambda: tmp_path)

    base_config = config_module.load_base_config()

    assert base_config["years_to_plan_for"] == 1
    assert base_config["onprem_cost_usd_per_tb_year"] == 20.0
    assert "gfs_overhead_factor" not in base_config
    assert "vul_price_per_instance_usd" not in base_config
    assert "aws_s3_cost_per_tb_month" not in base_config
    assert "objectfirst_cost_per_tb_month" not in base_config
