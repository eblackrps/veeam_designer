from veeam_designer.licensing import estimate_license
from veeam_designer.models import LicenseInput


def test_community_tier():
    lin = LicenseInput(vm_count=5)
    r = estimate_license(lin)
    assert r.tier == "community"
    assert r.annual_maintenance_usd == 0.0


def test_standard_tier():
    lin = LicenseInput(vm_count=100)
    r = estimate_license(lin)
    assert r.tier == "standard"
    assert r.annual_maintenance_usd > 0


def test_enterprise_tier():
    lin = LicenseInput(vm_count=600)
    r = estimate_license(lin)
    assert r.tier == "enterprise"


def test_nas_tb_counts_as_instances():
    lin = LicenseInput(vm_count=0, nas_tb=50.0)
    r = estimate_license(lin)
    assert r.protected_workloads == 50
