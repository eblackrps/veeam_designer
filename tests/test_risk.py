from veeam_designer.risk import (
    score_growth_risk,
    score_immutability_risk,
    score_proxy_risk,
    score_repo_risk,
    score_rpo_margin_risk,
    score_wan_risk,
)


def test_risk_low_repo():
    assert score_repo_risk(50.0) == 0


def test_risk_high_repo():
    assert score_repo_risk(2000.0) > score_repo_risk(100.0)


def test_wan_meets_target():
    assert score_wan_risk(True) == 0


def test_wan_fails_target():
    assert score_wan_risk(False) > 0


def test_proxy_adequate():
    assert score_proxy_risk(100, 100) == 0


def test_proxy_under_provisioned():
    assert score_proxy_risk(100, 10) > 0


def test_growth_low():
    assert score_growth_risk(5.0) == 0


def test_growth_high():
    assert score_growth_risk(25.0) > score_growth_risk(5.0)


def test_immutability_object_no_immut():
    assert score_immutability_risk(False, "object") > 0


def test_immutability_object_with_immut():
    assert score_immutability_risk(True, "object") == 0


def test_rpo_margin_within_budget():
    assert score_rpo_margin_risk(100.0, 200.0, 24.0, 12.0) == 0


def test_rpo_margin_over_budget():
    assert score_rpo_margin_risk(500.0, 100.0, 4.0, 20.0) > 0
