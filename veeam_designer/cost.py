from __future__ import annotations
from .models import RepoSizing, SobrDesign, CostEstimate, VeeamInput
from .config import CONFIG


# ---------------------------------------------------------------------------
# Round 9: multi-cloud provider registry
# ---------------------------------------------------------------------------

_CLOUD_PROVIDERS = {
    "aws_s3":      "aws_s3_cost_per_tb_month",
    "azure_blob":  "azure_blob_cost_per_tb_month",
    "wasabi":      "wasabi_cost_per_tb_month",
    "objectfirst": "objectfirst_cost_per_tb_month",
}


def _provider_rate(key: str, default: float) -> float:
    return float(CONFIG.get(key, default))


def estimate_costs(repo: RepoSizing, sobr: SobrDesign, vin: VeeamInput) -> CostEstimate:
    """
    Estimate infrastructure costs for the design.

    Year 1 costs are returned as monthly_object_usd / yearly_object_usd /
    yearly_onprem_usd for backwards-compatible output.

    Round 9 additions:
      - cloud_comparison: {provider: year-1 cost USD} for all cloud options
      - three_year_tco: {onprem: total, <best_cloud>: total, provider: name}
      - break_even_years: float — when cloud cumulative = onprem cumulative
    """
    object_cost_per_tb_month = float(CONFIG.get("object_cost_usd_per_tb_month", 20.0))
    onprem_cost_per_tb_year = float(CONFIG.get("onprem_cost_usd_per_tb_year", 20.0))
    annual_growth = vin.annual_growth_percent / 100.0

    # Capacity tier TB (Round 5)
    capacity_tb = sobr.capacity_tier_tb if (
        vin.capacity_tier_enabled or vin.direct_to_object
    ) else 0.0

    onprem_tb = max(0.0, repo.total_repo_tb - capacity_tb)

    # Year-1 costs
    monthly_object_usd = capacity_tb * object_cost_per_tb_month
    yearly_object_usd = monthly_object_usd * 12
    yearly_onprem_usd = onprem_tb * onprem_cost_per_tb_year

    notes: list[str] = []
    if capacity_tb > 0:
        notes.append(
            f"{capacity_tb:.1f} TB in object/capacity tier at "
            f"${object_cost_per_tb_month:.2f}/TB/month "
            f"(${monthly_object_usd:.2f}/mo, ${yearly_object_usd:.2f}/yr)."
        )
    if onprem_tb > 0:
        notes.append(
            f"{onprem_tb:.1f} TB on-premises at "
            f"${onprem_cost_per_tb_year:.2f}/TB/yr "
            f"(${yearly_onprem_usd:.2f}/yr)."
        )

    # ---------------------------------------------------------------------------
    # Round 9: 3-year TCO
    # ---------------------------------------------------------------------------

    def _three_year(yearly_yr1: float) -> float:
        total = 0.0
        for y in range(3):
            total += yearly_yr1 * ((1.0 + annual_growth) ** y)
        return round(total, 2)

    tco_onprem = _three_year(yearly_onprem_usd + yearly_object_usd)

    # Cloud comparison: use capacity_tb if set, else full repo TB
    cloud_tb = capacity_tb if capacity_tb > 0 else repo.total_repo_tb
    cloud_comparison: dict[str, float] = {}
    for provider, cfg_key in _CLOUD_PROVIDERS.items():
        rate = _provider_rate(cfg_key, object_cost_per_tb_month)
        cloud_comparison[provider] = round(cloud_tb * rate * 12, 2)

    # Best cloud (lowest year-1 cost)
    best_provider = min(cloud_comparison, key=cloud_comparison.get)
    best_rate = _provider_rate(_CLOUD_PROVIDERS[best_provider], object_cost_per_tb_month)
    best_cloud_yr1 = cloud_tb * best_rate * 12
    onprem_residual_yr1 = onprem_tb * onprem_cost_per_tb_year
    tco_best_cloud = _three_year(best_cloud_yr1 + onprem_residual_yr1)

    three_year_tco: dict[str, float] = {
        "onprem": tco_onprem,
        best_provider: tco_best_cloud,
        "provider": best_provider,
    }

    # Break-even calculation
    if tco_best_cloud < tco_onprem:
        break_even_years = 0.0
    else:
        break_even_years = 10.0
        cum_onprem = 0.0
        cum_cloud = 0.0
        for y in range(1, 11):
            growth = (1.0 + annual_growth) ** (y - 1)
            cum_onprem += (yearly_onprem_usd + yearly_object_usd) * growth
            cum_cloud += (best_cloud_yr1 + onprem_residual_yr1) * growth
            if cum_cloud <= cum_onprem:
                break_even_years = float(y)
                break

    notes.append(
        f"3-year TCO — On-prem: ${tco_onprem:,.0f} | "
        f"Best cloud ({best_provider}): ${tco_best_cloud:,.0f}. "
        f"Break-even: {'< 1 yr' if break_even_years == 0 else f'{break_even_years:.0f} yr(s)'}."
    )

    return CostEstimate(
        monthly_object_usd=round(monthly_object_usd, 2),
        yearly_object_usd=round(yearly_object_usd, 2),
        yearly_onprem_usd=round(yearly_onprem_usd, 2),
        notes=notes,
        cloud_comparison=cloud_comparison,
        three_year_tco=three_year_tco,
        break_even_years=round(break_even_years, 1),
    )
