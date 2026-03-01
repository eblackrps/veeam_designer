from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .models import VeeamDesign
from .config import CONFIG


@dataclass
class RiskSummary:
    level: str           # "green" / "yellow" / "red"
    total_score: int     # aggregate numeric score
    details: Dict[str, int]  # {"repo": int, "wan": int, "proxies": int}


def score_repo_risk(total_repo_tb: float) -> int:
    """
    Score repo risk based on total footprint and configured warning threshold.
    0 = green, 1 = yellow, 2 = red.
    """
    warn_tb = float(CONFIG.get("warn_repo_tb", 300.0))

    if total_repo_tb < warn_tb:
        return 0
    elif total_repo_tb < warn_tb * 2:
        return 1
    else:
        return 2


def score_wan_risk(meets_target: bool) -> int:
    """
    Simple WAN risk:
      - 0 if RPO target is met
      - 2 if RPO target is not met
    """
    return 0 if meets_target else 2


def score_proxy_risk(vm_count: int, total_tasks: int) -> int:
    """
    Score proxy sizing:
      - 0 if total tasks >= VM count      (1 task per VM or better)
      - 1 if total tasks >= VM count / 2  (1 task per 2 VMs)
      - 2 otherwise                       (under-provisioned)
    """
    if vm_count <= 0:
        return 0

    if total_tasks >= vm_count:
        return 0
    elif total_tasks >= vm_count / 2:
        return 1
    else:
        return 2


def compute_risk(design: VeeamDesign) -> RiskSummary:
    """
    Aggregate risk scoring for repo, WAN, and proxies,
    returning a RiskSummary that matches what print_human_summary expects.
    """
    repo_score = score_repo_risk(design.repo.total_repo_tb)
    wan_score = score_wan_risk(design.network.meets_target)
    proxy_score = score_proxy_risk(
        design.input.vm_count,
        design.roles.proxies.total_parallel_tasks,
    )

    details = {
        "repo": repo_score,
        "wan": wan_score,
        "proxies": proxy_score,
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
