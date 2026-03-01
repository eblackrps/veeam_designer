from __future__ import annotations
from .models import RepoSizing, CostEstimate
from .config import CONFIG


def estimate_costs(repo: RepoSizing) -> CostEstimate:
    """
    Estimate rough cost for the design.

    Current behavior:
      - Object storage cost is assumed to be 0 TB (no capacity tier modeled yet).
      - On-prem cost is based on the full repo footprint.
    
    This avoids referencing attributes that don't exist on RepoSizing
    (e.g., capacity_tier_tb) and keeps the model simple and safe.
    """

    object_cost_per_tb_month = CONFIG.get("object_cost_usd_per_tb_month", 20.0)
    onprem_cost_per_tb_year = CONFIG.get("onprem_cost_usd_per_tb_year", 20.0)

    # No capacity tier is modeled at the RepoSizing level yet,
    # so we assume 0 TB stored in object/capacity tier.
    object_tb = 0.0

    # Monthly and yearly object storage cost (will be $0.00 until capacity tier is modeled)
    monthly_object_usd = object_tb * object_cost_per_tb_month
    yearly_object_usd = monthly_object_usd * 12

    # On-prem costs based on total repo capacity (all on disk)
    yearly_onprem_usd = repo.total_repo_tb * onprem_cost_per_tb_year

    return CostEstimate(
        monthly_object_usd=round(monthly_object_usd, 2),
        yearly_object_usd=round(yearly_object_usd, 2),
        yearly_onprem_usd=round(yearly_onprem_usd, 2),
    )
