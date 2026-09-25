from __future__ import annotations

from .config import CONFIG
from .models import CostEstimate, RepoSizing, SobrDesign, VeeamInput

_CLOUD_PROVIDERS = {
    "aws_s3": "aws_s3_cost_per_tb_month",
    "azure_blob": "azure_blob_cost_per_tb_month",
    "wasabi": "wasabi_cost_per_tb_month",
    "objectfirst": "objectfirst_cost_per_tb_month",
}


def _rate(key: str) -> float:
    return max(0.0, float(CONFIG.get(key, 0.0)))


def estimate_costs(repo: RepoSizing, sobr: SobrDesign, vin: VeeamInput) -> CostEstimate:
    """Calculate cost only from explicitly configured rates; never embed market pricing."""

    object_rate = _rate("object_cost_usd_per_tb_month")
    onprem_rate = _rate("onprem_cost_usd_per_tb_year")
    provider_rates = {
        provider: _rate(config_key)
        for provider, config_key in _CLOUD_PROVIDERS.items()
        if _rate(config_key) > 0
    }

    configured = object_rate > 0 or onprem_rate > 0 or bool(provider_rates)
    if not configured:
        return CostEstimate(
            monthly_object_usd=0.0,
            yearly_object_usd=0.0,
            yearly_onprem_usd=0.0,
            configured=False,
            notes=[
                "Cost model is not configured. No live cloud, hardware, licensing, or contract "
                "pricing is assumed by Veeam Designer."
            ],
            cloud_comparison={},
            three_year_tco={},
            break_even_years=0.0,
        )

    annual_growth = max(-1.0, vin.annual_growth_percent / 100.0)
    capacity_tb = (
        sobr.capacity_tier_tb if (vin.capacity_tier_enabled or vin.direct_to_object) else 0.0
    )
    onprem_tb = max(0.0, repo.total_repo_tb - capacity_tb)

    monthly_object_usd = capacity_tb * object_rate if object_rate > 0 else 0.0
    yearly_object_usd = monthly_object_usd * 12.0
    yearly_onprem_usd = onprem_tb * onprem_rate if onprem_rate > 0 else 0.0

    def _three_year(year_one: float) -> float:
        return round(sum(year_one * ((1.0 + annual_growth) ** year) for year in range(3)), 2)

    base_year_one = yearly_onprem_usd + yearly_object_usd
    three_year_tco: dict[str, float | str] = {}
    if base_year_one > 0:
        three_year_tco["configured_design"] = _three_year(base_year_one)

    cloud_tb = capacity_tb if capacity_tb > 0 else repo.total_repo_tb
    cloud_comparison = {
        provider: round(cloud_tb * rate * 12.0, 2)
        for provider, rate in provider_rates.items()
    }

    break_even_years = 0.0
    if cloud_comparison and onprem_rate > 0:
        best_provider = min(cloud_comparison, key=cloud_comparison.get)
        best_cloud_year_one = cloud_comparison[best_provider]
        onprem_all_year_one = repo.total_repo_tb * onprem_rate
        three_year_tco["onprem_all"] = _three_year(onprem_all_year_one)
        three_year_tco[best_provider] = _three_year(best_cloud_year_one)
        three_year_tco["provider"] = best_provider

        if best_cloud_year_one >= onprem_all_year_one:
            break_even_years = 10.0
            cumulative_onprem = 0.0
            cumulative_cloud = 0.0
            for year in range(1, 11):
                growth = (1.0 + annual_growth) ** (year - 1)
                cumulative_onprem += onprem_all_year_one * growth
                cumulative_cloud += best_cloud_year_one * growth
                if cumulative_cloud <= cumulative_onprem:
                    break_even_years = float(year)
                    break

    notes = [
        "Cost output uses only rates explicitly configured in config.json. Values do not include "
        "egress, API operations, support, hardware maintenance, power, facilities, discounts, or taxes."
    ]
    if object_rate <= 0 and capacity_tb > 0:
        notes.append("Object-storage rate is not configured; object cost is omitted.")
    if onprem_rate <= 0 and onprem_tb > 0:
        notes.append("On-premises $/TB/year rate is not configured; on-premises cost is omitted.")

    return CostEstimate(
        monthly_object_usd=round(monthly_object_usd, 2),
        yearly_object_usd=round(yearly_object_usd, 2),
        yearly_onprem_usd=round(yearly_onprem_usd, 2),
        configured=True,
        notes=notes,
        cloud_comparison=cloud_comparison,
        three_year_tco=three_year_tco,
        break_even_years=round(break_even_years, 1),
    )
