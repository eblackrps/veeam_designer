from typing import List

from .models import (
    Blueprint,
    CostEstimate,
    JobSet,
    NetworkPlan,
    RepoPerfModel,
    RolePlan,
    SobrDesign,
)


def build_blueprint(
    roles: RolePlan,
    jobs: JobSet,
    sobr: SobrDesign,
    repo_perf: RepoPerfModel,
    network: NetworkPlan,
    cost: CostEstimate,
) -> Blueprint:
    notes: List[str] = []

    notes.append(
        "Blueprint generated: review roles, jobs, and WAN assumptions before implementation."
    )
    if not network.meets_target:
        notes.append(
            "WAN does not meet target RPO; prioritize replication/copy redesign or bandwidth upgrade."
        )
    if sobr.capacity_tier_tb > 0:
        notes.append(
            "Capacity tier is in use; ensure object storage is hardened and properly secured."
        )

    return Blueprint(
        role_plan=roles,
        jobs=jobs,
        sobr=sobr,
        repo_perf=repo_perf,
        network=network,
        cost=cost,
        notes=notes,
    )
