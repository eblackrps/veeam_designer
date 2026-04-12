from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .config import CONFIG
from .models import VeeamDesign


@dataclass
class RiskSummary:
    level: str  # "green" / "yellow" / "red"
    total_score: int  # aggregate numeric score
    details: Dict[str, int]  # {"repo": int, "wan": int, "proxies": int, ...}


def score_repo_risk(total_repo_tb: float) -> int:
    warn_tb = float(CONFIG.get("warn_repo_tb", 300.0))
    if total_repo_tb < warn_tb:
        return 0
    elif total_repo_tb < warn_tb * 2:
        return 1
    else:
        return 2


def score_wan_risk(meets_target: bool) -> int:
    return 0 if meets_target else 2


def score_proxy_risk(vm_count: int, total_tasks: int) -> int:
    if vm_count <= 0:
        return 0
    if total_tasks >= vm_count:
        return 0
    elif total_tasks >= vm_count / 2:
        return 1
    else:
        return 2


def score_growth_risk(annual_growth_pct: float) -> int:
    """
    Round 9: growth forecast risk.
    > 20% growth/yr → red; 10–20% → yellow; else green.
    """
    if annual_growth_pct > 20.0:
        return 2
    elif annual_growth_pct > 10.0:
        return 1
    return 0


def score_immutability_risk(immutability_enabled: bool, repo_type: str) -> int:
    """
    Round 9: flag when object storage is chosen but immutability is off.
    Object storage without immutability is a compliance gap.
    """
    if repo_type == "object" and not immutability_enabled:
        return 1
    return 0


def score_rpo_margin_risk(
    required_mbps: float,
    wan_mbps: float,
    target_rpo_hours: float,
    achievable_rpo_hours: float,
) -> int:
    """
    Round 9: weighted RPO achievability based on how far over bandwidth we are.
    """
    if wan_mbps <= 0:
        return 0  # no WAN configured — not penalised
    if required_mbps <= wan_mbps:
        return 0
    # Ratio of excess demand to available bandwidth
    excess_ratio = (required_mbps - wan_mbps) / wan_mbps
    if excess_ratio > 0.5:
        return 2
    return 1


def compute_risk(design: VeeamDesign) -> RiskSummary:
    """
    Aggregate risk scoring, returning a RiskSummary compatible with
    models.RiskScore (same fields, used via duck-typing).
    """
    repo_score = score_repo_risk(design.repo.total_repo_tb)
    wan_score = score_wan_risk(design.network.meets_target)
    proxy_score = score_proxy_risk(
        design.input.vm_count,
        design.roles.proxies.total_parallel_tasks,
    )
    growth_score = score_growth_risk(design.input.annual_growth_percent)
    immutability_score = score_immutability_risk(
        design.input.immutability_enabled,
        design.input.repo_type,
    )
    rpo_score = score_rpo_margin_risk(
        required_mbps=design.network.required_mbps,
        wan_mbps=design.input.wan_bandwidth_mbps,
        target_rpo_hours=design.input.target_rpo_hours,
        achievable_rpo_hours=design.network.achievable_rpo_hours,
    )

    details = {
        "repo": repo_score,
        "wan": wan_score,
        "proxies": proxy_score,
        "growth": growth_score,
        "immutability": immutability_score,
        "rpo_margin": rpo_score,
    }

    total_score = sum(details.values())

    if total_score <= 1:
        level = "green"
    elif total_score <= 4:
        level = "yellow"
    else:
        level = "red"

    return RiskSummary(
        level=level,
        total_score=total_score,
        details=details,
    )
