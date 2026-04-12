"""Compliance framework gap analysis for Veeam backup configurations."""

from __future__ import annotations

from .models import ComplianceInput, ComplianceResult

FRAMEWORKS: dict[str, dict] = {
    "hipaa": {
        "name": "HIPAA",
        "min_retention_days": 2190,
        "immutability_required": True,
        "encryption_required": True,
        "offsite_copy_required": True,
        "rpo_max_hours": 24.0,
    },
    "soc2": {
        "name": "SOC 2",
        "min_retention_days": 365,
        "immutability_required": False,
        "encryption_required": True,
        "offsite_copy_required": True,
        "rpo_max_hours": 4.0,
    },
    "gdpr": {
        "name": "GDPR",
        "min_retention_days": 30,
        "immutability_required": False,
        "encryption_required": True,
        "offsite_copy_required": False,
        "rpo_max_hours": 24.0,
    },
    "pci_dss": {
        "name": "PCI DSS",
        "min_retention_days": 365,
        "immutability_required": True,
        "encryption_required": True,
        "offsite_copy_required": True,
        "rpo_max_hours": 4.0,
    },
    "dora": {
        "name": "DORA",
        "min_retention_days": 730,
        "immutability_required": True,
        "encryption_required": True,
        "offsite_copy_required": True,
        "rpo_max_hours": 4.0,
    },
}


def check_compliance(cin: ComplianceInput) -> ComplianceResult:
    """Check if configuration meets a regulatory framework's minimum requirements."""
    if cin.framework == "none":
        return ComplianceResult(
            framework="none",
            compliant=True,
            gaps=[],
            recommended_retention_days=cin.current_retention_days,
            risk_level="compliant",
        )

    if cin.framework not in FRAMEWORKS:
        return ComplianceResult(
            framework=cin.framework,
            compliant=False,
            gaps=[
                f"Unknown compliance framework '{cin.framework}'. "
                f"Supported: {', '.join(FRAMEWORKS.keys())}."
            ],
            recommended_retention_days=cin.current_retention_days,
            risk_level="non-compliant",
        )

    fw = FRAMEWORKS[cin.framework]
    gaps = []

    if cin.current_retention_days < fw["min_retention_days"]:
        gaps.append(
            f"Retention {cin.current_retention_days}d < required {fw['min_retention_days']}d "
            f"for {fw['name']}."
        )
    if fw["immutability_required"] and not cin.immutability_enabled:
        gaps.append(f"Immutability required by {fw['name']} but not enabled.")
    if fw["encryption_required"] and not cin.encryption_enabled:
        gaps.append(f"Encryption required by {fw['name']} but not enabled.")
    if fw["offsite_copy_required"] and not cin.offsite_copy_enabled:
        gaps.append(f"Offsite backup copy required by {fw['name']} but not configured.")
    if cin.target_rpo_hours > fw["rpo_max_hours"]:
        gaps.append(
            f"Target RPO {cin.target_rpo_hours:.0f}h exceeds {fw['name']} maximum "
            f"{fw['rpo_max_hours']:.0f}h."
        )

    compliant = len(gaps) == 0
    if compliant:
        risk_level = "compliant"
    elif len(gaps) <= 1:
        risk_level = "partial"
    else:
        risk_level = "non-compliant"

    return ComplianceResult(
        framework=cin.framework,
        compliant=compliant,
        gaps=gaps,
        recommended_retention_days=fw["min_retention_days"],
        risk_level=risk_level,
    )
