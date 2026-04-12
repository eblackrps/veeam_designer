from veeam_designer.models import WanAccelInput
from veeam_designer.wan_accel import size_wan_accel


def test_wan_accel_basic():
    win = WanAccelInput(source_tb=100.0, wan_mbps=100.0)
    r = size_wan_accel(win)
    assert r.source_appliance_count >= 1
    assert r.cache_size_gb_per_source > 0
    assert r.source_digest_gb_per_source == 2000
    assert r.target_digest_gb_per_target == 2000
    assert r.target_total_free_space_gb == 2100


def test_effective_mbps_higher():
    win = WanAccelInput(source_tb=100.0, wan_mbps=100.0, dedupe_ratio=3.0, compression_ratio=1.6)
    r = size_wan_accel(win)
    assert r.effective_mbps > win.wan_mbps


def test_zero_wan_returns_skip():
    win = WanAccelInput(source_tb=100.0, wan_mbps=0.0)
    r = size_wan_accel(win)
    assert r.source_appliance_count == 0
    assert len(r.notes) > 0


def test_high_effective_throughput_requires_multiple_pairs():
    win = WanAccelInput(
        source_tb=100.0,
        wan_mbps=200.0,
        dedupe_ratio=4.0,
        compression_ratio=2.0,
    )
    r = size_wan_accel(win)
    assert r.effective_mbps == 1600.0
    assert r.source_appliance_count == 4
    assert r.target_appliance_count == 4
