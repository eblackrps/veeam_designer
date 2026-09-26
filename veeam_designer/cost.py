from __future__ import annotations

from .models import CostEstimate, RepoSizing, SobrDesign, VeeamInput


def estimate_costs(repo: RepoSizing, sobr: SobrDesign, vin: VeeamInput) -> CostEstimate:
    """Estimate configured storage planning costs from explicit rates and tier policy."""

    object_rate = max(0.0, float(vin.object_cost_usd_per_tb_month))
    onprem_rate = max(0.0, float(vin.onprem_cost_usd_per_tb_year))

    is_object_target = vin.repo_type == "object" or vin.direct_to_object
    policy = (sobr.capacity_tier_policy or vin.capacity_tier_policy or "none").strip().lower()

    object_tb = max(0.0, sobr.capacity_tier_tb)
    if is_object_target:
        local_tb = 0.0
    elif vin.capacity_tier_enabled:
        local_tb = max(0.0, sobr.performance_tier_tb)
    else:
        local_tb = max(0.0, repo.total_repo_tb)

    monthly_object_usd = object_tb * object_rate
    yearly_object_usd = monthly_object_usd * 12.0
    yearly_onprem_usd = local_tb * onprem_rate
    total_yearly_usd = yearly_object_usd + yearly_onprem_usd

    notes: list[str] = [
        "Storage cost values use explicit planning rates; they are not live Veeam, cloud-provider, "
        "or storage-vendor quotes."
    ]
    if object_tb > 0:
        notes.append(
            f"{object_tb:.1f} TB object capacity at " + "$" + f"{object_rate:.2f}/modeled-TB/month."
        )
    if local_tb > 0:
        notes.append(
            f"{local_tb:.1f} TB local capacity at " + "$" + f"{onprem_rate:.2f}/modeled-TB/year."
        )

    if vin.capacity_tier_immutable and object_tb > 0:
        notes.append(
            "Capacity Tier Object Lock is enabled. The object-storage dollar amount is a base "
            "modeled footprint. Actual billed storage may be higher because expired blocks can "
            "remain immutable until their immutability and Block Generation periods expire. "
            "No arbitrary percentage uplift is added."
        )

    if policy == "copy":
        notes.append(
            "Capacity Tier Copy is additive for storage planning: the copied object footprint "
            "does not reduce the local performance-tier capacity."
        )
    elif policy == "move":
        notes.append(
            "Capacity Tier Move local capacity is derived from sealed-chain restore points that "
            "are older than the configured operational restore window; no percentage offload "
            "assumption is used."
        )
    elif policy == "copy_move":
        notes.append(
            "Capacity Tier Copy + Move models the retained/GFS object copy and removes from local "
            "capacity only the sealed short-term data that is older than the configured "
            "operational restore window."
        )

    notes.append(
        "API operations, retrieval/egress, minimum-storage-duration charges, taxes, hardware "
        "acquisition, support, power, rack space, and discounts are outside this storage-rate model."
    )

    return CostEstimate(
        monthly_object_usd=round(monthly_object_usd, 2),
        yearly_object_usd=round(yearly_object_usd, 2),
        yearly_onprem_usd=round(yearly_onprem_usd, 2),
        total_yearly_usd=round(total_yearly_usd, 2),
        notes=notes,
        cloud_comparison={},
        three_year_tco={},
        break_even_years=0.0,
    )
