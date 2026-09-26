from __future__ import annotations

from .config import CONFIG
from .models import CostEstimate, RepoSizing, SobrDesign, VeeamInput

# ---------------------------------------------------------------------------
# Round 9: multi-cloud provider registry
# ---------------------------------------------------------------------------

def estimate_costs(repo: RepoSizing, sobr: SobrDesign, vin: VeeamInput) -> CostEstimate:
    """Estimate configured infrastructure planning costs.

    The rates are explicit configuration assumptions. This function does not infer live cloud
    pricing, provider discounts, hardware acquisition cost, or a cloud break-even point.
    """

    object_cost_per_tb_month = float(CONFIG.get("object_cost_usd_per_tb_month", 20.0))
    onprem_cost_per_tb_year = float(CONFIG.get("onprem_cost_usd_per_tb_year", 20.0))

    is_object_target = vin.repo_type == "object" or vin.direct_to_object
    capacity_tb = sobr.capacity_tier_tb if (vin.capacity_tier_enabled or is_object_target) else 0.0
    onprem_tb = max(0.0, repo.total_repo_tb - capacity_tb)

    monthly_object_usd = capacity_tb * object_cost_per_tb_month
    yearly_object_usd = monthly_object_usd * 12.0
    yearly_onprem_usd = onprem_tb * onprem_cost_per_tb_year

    notes: list[str] = [
        "Cost values use configured planning rates only; they are not Veeam, cloud-provider, "
        "or storage-vendor quotes."
    ]
    if capacity_tb > 0:
        notes.append(
            f"{capacity_tb:.1f} TB object capacity at the configured "
            f"${object_cost_per_tb_month:.2f}/TB/month planning rate."
        )
    if onprem_tb > 0:
        notes.append(
            f"{onprem_tb:.1f} TB on-premises at the configured "
            f"${onprem_cost_per_tb_year:.2f}/TB/year planning rate."
        )

    return CostEstimate(
        monthly_object_usd=round(monthly_object_usd, 2),
        yearly_object_usd=round(yearly_object_usd, 2),
        yearly_onprem_usd=round(yearly_onprem_usd, 2),
        notes=notes,
        cloud_comparison={},
        three_year_tco={},
        break_even_years=0.0,
    )
