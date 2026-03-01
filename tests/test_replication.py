from veeam_designer.models import ReplicationInput
from veeam_designer.replication import size_replication


def test_replication_basic():
    rin = ReplicationInput(source_tb=50.0, vm_count=100, wan_mbps=1000.0)
    r = size_replication(rin)
    assert r.replica_storage_tb > 0
    assert r.required_mbps > 0


def test_cdp_adds_journal():
    rin = ReplicationInput(source_tb=50.0, vm_count=100, wan_mbps=1000.0, cdp_enabled=True)
    r = size_replication(rin)
    assert r.cdp_proxy_cores > 0
    assert r.cdp_journal_tb > 0


def test_low_wan_fails_rpo():
    rin = ReplicationInput(source_tb=200.0, vm_count=500, wan_mbps=10.0, rpo_hours=1.0)
    r = size_replication(rin)
    assert not r.meets_rpo
