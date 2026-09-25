from veeam_designer.models import WanAccelInput
from veeam_designer.wan_accel import size_wan_accel


def test_auto_uses_low_bandwidth_mode_at_100_mbps_known_answer():
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
    assert result.source_digest_gb_per_source == 2000
    assert result.target_digest_gb_per_target == 2000
    assert result.cache_size_gb_per_source == 100
    assert result.target_total_free_space_gb == 2100


def test_auto_uses_direct_above_100_mbps():
    result = size_wan_accel(
        WanAccelInput(
            source_tb=100.0,
            wan_mbps=200.0,
            daily_change_pct=5.0,
        )
    )

    assert result.mode == "direct"
    assert result.source_appliance_count == 0
    assert result.target_appliance_count == 0
    assert result.target_total_free_space_gb == 0


def test_explicit_high_bandwidth_mode_uses_one_percent_digests_no_cache():
    result = size_wan_accel(
        WanAccelInput(
            source_tb=100.0,
            wan_mbps=200.0,
            daily_change_pct=5.0,
            mode="high",
        )
    )

    assert result.mode == "high"
    assert result.source_appliance_count == 1
    assert result.target_appliance_count == 1
    assert result.source_digest_gb_per_source == 1000
    assert result.target_digest_gb_per_target == 1000
    assert result.cache_size_gb_per_source == 0
    assert result.target_total_free_space_gb == 1000


def test_low_bandwidth_cache_respects_guest_os_and_vendor_minimum():
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


def test_accelerator_pairs_scale_from_raw_processing_demand():
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
    assert result.source_digest_gb_per_source == 2000
    assert result.target_digest_gb_per_target == 2000
    assert result.target_total_free_space_gb == 6300


def test_copy_interval_scales_changed_data_known_answer():
    result = size_wan_accel(
        WanAccelInput(
            source_tb=100.0,
            wan_mbps=100.0,
            backup_copy_frequency_hours=12.0,
            daily_change_pct=5.0,
            mode="low",
            dedupe_ratio=1.0,
            compression_ratio=1.0,
        )
    )

    assert result.backup_copy_window_hours == 58.25
    assert result.meets_copy_window is False


def test_low_mode_uses_supplied_reduction_as_planning_assumption():
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


def test_high_mode_does_not_apply_global_cache_dedupe_ratio():
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


def test_zero_wan_returns_non_feasible_result():
    result = size_wan_accel(WanAccelInput(source_tb=100.0, wan_mbps=0.0))

    assert result.source_appliance_count == 0
    assert result.meets_copy_window is False
    assert result.notes
