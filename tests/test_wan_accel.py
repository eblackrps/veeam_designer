from veeam_designer.models import WanAccelInput
from veeam_designer.wan_accel import size_wan_accel


def test_auto_uses_low_bandwidth_mode_at_100_mbps():
    result = size_wan_accel(
        WanAccelInput(
            source_tb=100.0,
            wan_mbps=100.0,
            daily_change_pct=5.0,
        )
    )

    assert result.mode == "low"
    assert result.source_appliance_count == 1
    assert result.target_appliance_count == 1
    assert result.source_digest_gb_per_source == 2048
    assert result.target_digest_gb_per_target == 2048
    assert result.cache_size_gb_per_source == 100
    assert result.target_total_free_space_gb == 2148


def test_auto_uses_high_bandwidth_mode_above_100_mbps():
    result = size_wan_accel(
        WanAccelInput(
            source_tb=100.0,
            wan_mbps=200.0,
            daily_change_pct=5.0,
        )
    )

    assert result.mode == "high"
    assert result.source_appliance_count == 1
    assert result.target_appliance_count == 1
    assert result.source_digest_gb_per_source == 1024
    assert result.target_digest_gb_per_target == 1024
    assert result.cache_size_gb_per_source == 0
    assert result.target_total_free_space_gb == 1024


def test_low_bandwidth_cache_respects_guest_os_minimum():
    result = size_wan_accel(
        WanAccelInput(
            source_tb=10.0,
            wan_mbps=50.0,
            mode="low",
            os_type_count=5,
            cache_size_gb_per_source=0,
        )
    )

    assert result.cache_size_gb_per_source == 50


def test_low_mode_uses_dedupe_and_compression_reduction_inputs():
    result = size_wan_accel(
        WanAccelInput(
            source_tb=100.0,
            wan_mbps=100.0,
            mode="low",
            dedupe_ratio=3.0,
            compression_ratio=1.6,
        )
    )

    assert result.effective_mbps == 480.0


def test_high_mode_uses_compression_but_not_global_cache_dedupe():
    result = size_wan_accel(
        WanAccelInput(
            source_tb=100.0,
            wan_mbps=200.0,
            mode="high",
            dedupe_ratio=4.0,
            compression_ratio=2.0,
        )
    )

    assert result.effective_mbps == 400.0
    assert result.cache_size_gb_per_source == 0


def test_accelerator_pairs_scale_from_source_processing_demand():
    result = size_wan_accel(
        WanAccelInput(
            source_tb=300.0,
            wan_mbps=100.0,
            mode="low",
            daily_change_pct=5.0,
        )
    )

    assert result.source_appliance_count == 3
    assert result.target_appliance_count == 3
    assert result.source_digest_gb_per_source == 2048
    assert result.target_total_free_space_gb == (3 * 100) + (3 * 2048)


def test_direct_mode_allocates_no_wan_accelerator_service_data():
    result = size_wan_accel(
        WanAccelInput(
            source_tb=100.0,
            wan_mbps=1000.0,
            mode="direct",
        )
    )

    assert result.mode == "direct"
    assert result.source_appliance_count == 0
    assert result.target_appliance_count == 0
    assert result.source_digest_gb_per_source == 0
    assert result.target_digest_gb_per_target == 0
    assert result.target_total_free_space_gb == 0


def test_zero_wan_returns_non_feasible_result():
    result = size_wan_accel(WanAccelInput(source_tb=100.0, wan_mbps=0.0))

    assert result.source_appliance_count == 0
    assert result.meets_copy_window is False
    assert result.notes
