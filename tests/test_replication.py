from veeam_designer.models import ReplicationInput
from veeam_designer.replication import size_replication


def test_replication_average_change_rate_and_storage_baseline():
    rin = ReplicationInput(
        source_tb=50.0,
        vm_count=100,
        wan_mbps=1000.0,
        daily_change_pct=5.0,
    )
    result = size_replication(rin)

    assert result.required_mbps == 242.7
    assert result.meets_rpo is True
    assert result.replica_storage_tb == 50.0


def test_replication_bandwidth_is_independent_of_rpo_setting():
    one_hour = size_replication(
        ReplicationInput(
            source_tb=100.0,
            vm_count=100,
            wan_mbps=2000.0,
            rpo_hours=1.0,
            daily_change_pct=5.0,
        )
    )
    four_hour = size_replication(
        ReplicationInput(
            source_tb=100.0,
            vm_count=100,
            wan_mbps=2000.0,
            rpo_hours=4.0,
            daily_change_pct=5.0,
        )
    )

    assert one_hour.required_mbps == 485.5
    assert four_hour.required_mbps == 485.5


def test_cdp_journal_uses_short_term_retention_not_rpo_seconds():
    base = size_replication(
        ReplicationInput(
            source_tb=50.0,
            vm_count=100,
            wan_mbps=1000.0,
            cdp_enabled=True,
            rpo_seconds=15,
            cdp_retention_hours=12.0,
            daily_change_pct=5.0,
        )
    )
    faster_rpo = size_replication(
        ReplicationInput(
            source_tb=50.0,
            vm_count=100,
            wan_mbps=1000.0,
            cdp_enabled=True,
            rpo_seconds=5,
            cdp_retention_hours=12.0,
            daily_change_pct=5.0,
        )
    )

    assert base.cdp_journal_tb == 1.25
    assert faster_rpo.cdp_journal_tb == 1.25
    assert base.cdp_proxy_count_per_side == 1
    assert base.cdp_proxy_cores == 4
    assert base.cdp_proxy_ram_gb == 8
    assert base.cdp_proxy_cache_gb == 50


def test_cdp_journal_scales_with_retention_window():
    twelve = size_replication(
        ReplicationInput(
            source_tb=50.0,
            vm_count=100,
            wan_mbps=1000.0,
            cdp_enabled=True,
            cdp_retention_hours=12.0,
            daily_change_pct=5.0,
        )
    )
    twenty_four = size_replication(
        ReplicationInput(
            source_tb=50.0,
            vm_count=100,
            wan_mbps=1000.0,
            cdp_enabled=True,
            cdp_retention_hours=24.0,
            daily_change_pct=5.0,
        )
    )

    assert twelve.cdp_journal_tb == 1.25
    assert twenty_four.cdp_journal_tb == 2.5


def test_low_wan_fails_average_change_rate():
    result = size_replication(
        ReplicationInput(
            source_tb=200.0,
            vm_count=500,
            wan_mbps=10.0,
            daily_change_pct=5.0,
        )
    )

    assert result.required_mbps == 970.9
    assert result.meets_rpo is False
