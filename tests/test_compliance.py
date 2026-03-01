from veeam_designer.models import ComplianceInput
from veeam_designer.compliance import check_compliance


def test_none_framework_is_compliant():
    cin = ComplianceInput(framework="none", current_retention_days=30)
    r = check_compliance(cin)
    assert r.compliant is True


def test_hipaa_short_retention():
    cin = ComplianceInput(framework="hipaa", current_retention_days=365, immutability_enabled=True,
                          encryption_enabled=True, offsite_copy_enabled=True)
    r = check_compliance(cin)
    assert not r.compliant
    assert any("Retention" in g for g in r.gaps)


def test_hipaa_fully_compliant():
    cin = ComplianceInput(framework="hipaa", current_retention_days=2190, immutability_enabled=True,
                          encryption_enabled=True, offsite_copy_enabled=True, target_rpo_hours=24.0)
    r = check_compliance(cin)
    assert r.compliant


def test_gdpr_no_immutability_ok():
    cin = ComplianceInput(framework="gdpr", current_retention_days=365, immutability_enabled=False,
                          encryption_enabled=True)
    r = check_compliance(cin)
    assert r.compliant
