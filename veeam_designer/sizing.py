from typing import Dict, List
from .models import (
    VeeamInput,
    RepoSizing,
    VeeamDesign,
    MultiSiteDesign,
    SiteDesign,
)
from .config import CONFIG
from .jobs import build_jobs
from .roles import build_role_plan
from .sobr import design_sobr
from .repo_perf import estimate_repo_perf
from .network import build_network_plan
from .cost import estimate_costs
from .blueprint import build_blueprint
from .risk import compute_risk
from .orca import size_orca


def size_repository(vin: VeeamInput) -> RepoSizing:
    effective_total_tb = vin.total_data_tb * (
        1 + vin.annual_growth_percent / 100 * vin.years_to_plan_for
    )
    daily_change_tb = vin.total_data_tb * vin.daily_change_percent / 100

    weeks_in_retention = vin.primary_retention_days / 7.0
    week_full_tb = effective_total_tb
    week_incr_tb = daily_change_tb * 6
    week_total_tb = week_full_tb + week_incr_tb

    primary_logical_tb = week_total_tb * weeks_in_retention
    primary_physical_tb = primary_logical_tb / (vin.compression_ratio * vin.dedupe_ratio)
    primary_repo_tb = primary_physical_tb * CONFIG["repo_overhead_factor"]

    gfs_weekly_tb = vin.gfs_weekly_count * effective_total_tb / vin.compression_ratio
    gfs_monthly_tb = vin.gfs_monthly_count * effective_total_tb / vin.compression_ratio
    gfs_yearly_tb = vin.gfs_yearly_count * effective_total_tb / vin.compression_ratio
    gfs_repo_tb = (gfs_weekly_tb + gfs_monthly_tb + gfs_yearly_tb) * CONFIG["gfs_overhead_factor"]

    total_repo_tb = primary_repo_tb + gfs_repo_tb

    # Round 3: immutability adds ~5% for XFS extended attribute / object-lock metadata
    if vin.immutability_enabled:
        total_repo_tb *= 1.05

    return RepoSizing(
        primary_repo_tb=round(primary_repo_tb, 1),
        gfs_repo_tb=round(gfs_repo_tb, 1),
        total_repo_tb=round(total_repo_tb, 1),
    )


def design_veeam_environment(vin: VeeamInput) -> VeeamDesign:
    repo = size_repository(vin)
    jobs = build_jobs(vin)
    roles = build_role_plan(vin, repo)
    sobr = design_sobr(repo, vin)
    repo_perf = estimate_repo_perf(vin, repo, jobs)
    network = build_network_plan(vin, repo)
    cost = estimate_costs(repo, sobr, vin)

    notes: Dict[str, str] = {}

    if repo.total_repo_tb > CONFIG["warn_repo_tb"]:
        notes["repo"] = (
            "Total repo size exceeds configured threshold. Consider SOBR with multiple extents and/or "
            "object storage capacity tier with immutability."
        )

    if not network.meets_target:
        notes["wan"] = "WAN bandwidth does not meet target RPO; replication/copy jobs will lag behind."

    if vin.vm_count and roles.proxies.total_parallel_tasks < vin.vm_count / 3:
        notes["proxies"] = (
            "Proxy parallelism is low vs VM count. Consider more proxy cores or additional proxy VMs."
        )

    hv = vin.hypervisor.lower()
    if hv == "vmware":
        notes.setdefault(
            "platform",
            "VMware: align proxies with clusters, prefer DirectSAN or HotAdd where possible, "
            "and avoid NBD for large/high-churn workloads unless absolutely necessary.",
        )
    elif hv == "hyperv":
        notes.setdefault(
            "platform",
            "Hyper-V: prefer off-host proxies with SAN access for larger environments. "
            "Ensure Cluster Shared Volumes are visible to off-host proxies and coordinate "
            "VSS load on busy hosts.",
        )
    elif hv == "nutanix_ahv":
        notes.setdefault(
            "platform",
            "Nutanix AHV: deploy AHV proxy VMs with direct access to storage. "
            "Co-locate proxies with Nutanix clusters and size for parallelism per cluster, "
            "not just total VM count.",
        )
    elif hv == "agent":
        notes.setdefault(
            "platform",
            "Agent-based backups: treat these as network/volume workloads. "
            "Plan for higher overhead, longer windows, and ensure backup traffic is "
            "segmented from production where possible.",
        )

    # Round 4: ObjectFirst Orca sizing when repo_type is object storage
    orca = None
    if vin.repo_type == "object":
        orca = size_orca(
            total_protected_tb=repo.total_repo_tb,
            immutability_days=30 if vin.immutability_enabled else 0,
        )

    blueprint = build_blueprint(roles, jobs, sobr, repo_perf, network, cost)
    blueprint.orca = orca

    design = VeeamDesign(
        input=vin,
        repo=repo,
        roles=roles,
        jobs=jobs,
        sobr=sobr,
        repo_perf=repo_perf,
        network=network,
        cost=cost,
        blueprint=blueprint,
        risk=None,
        notes=notes,
        orca=orca,
    )

    design.risk = compute_risk(design)
    return design


def design_multi_site(sites: List[tuple[str, VeeamInput]]) -> MultiSiteDesign:
    site_designs: List[SiteDesign] = []
    total_repo_tb = 0.0
    aggregated_notes: Dict[str, str] = {}

    for name, vin in sites:
        d = design_veeam_environment(vin)
        site_designs.append(SiteDesign(name=name, design=d))
        total_repo_tb += d.repo.total_repo_tb

    if total_repo_tb > CONFIG["warn_repo_tb"]:
        aggregated_notes["sobr"] = (
            f"Combined repository footprint across all sites is {total_repo_tb:.1f} TB, "
            "which exceeds the configured threshold. Consider multi-site SOBR design."
        )

    return MultiSiteDesign(
        sites=site_designs,
        total_repo_tb=round(total_repo_tb, 1),
        notes=aggregated_notes,
    )
