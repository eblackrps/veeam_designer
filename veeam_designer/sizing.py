from typing import Dict, List
from .models import (
    VeeamInput,
    RepoSizing,
    VeeamDesign,
    MultiSiteDesign,
    SiteDesign,
    WanAccelInput,
    LicenseInput,
    VeeamOneInput,
    ComplianceInput,
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
from .replication import size_replication
from .nas import size_nas
from .wan_accel import size_wan_accel
from .licensing import estimate_license
from .tape import size_tape
from .veeam_one import size_veeam_one
from .compliance import check_compliance


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

    if vin.vm_count and roles.proxies.total_parallel_tasks < vin.vm_count / 10:
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

    # v3: replication sizing
    replication_design = size_replication(vin.replication_input) if vin.replication_input else None

    # v3: NAS sizing
    nas_design = size_nas(vin.nas_input) if vin.nas_input else None

    # v3: WAN accelerator sizing
    wan_accel_design = None
    if vin.wan_accel_input:
        wan_accel_design = size_wan_accel(vin.wan_accel_input)
    elif vin.wan_bandwidth_mbps > 0:
        wa_in = WanAccelInput(
            source_tb=vin.total_data_tb,
            wan_mbps=vin.wan_bandwidth_mbps,
            dedupe_ratio=vin.dedupe_ratio,
            compression_ratio=vin.compression_ratio,
        )
        wan_accel_design = size_wan_accel(wa_in)

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
    design.replication = replication_design
    design.nas = nas_design
    design.wan_accel = wan_accel_design

    # v3: license estimation
    lic_in = vin.license_input or LicenseInput(
        vm_count=vin.vm_count,
        physical_count=0,
        nas_tb=0.0,
        cloud_workloads=0,
        license_type="vul",
    )
    design.license_estimate = estimate_license(lic_in)

    # v3: tape sizing (optional)
    design.tape = size_tape(vin.tape_input) if vin.tape_input else None

    # v3: Veeam ONE sizing (auto-generate from vm_count)
    v1_in = vin.veeam_one_input or VeeamOneInput(protected_vms=vin.vm_count)
    design.veeam_one = size_veeam_one(v1_in)

    # v3: compliance check
    comp_in = ComplianceInput(
        framework=vin.compliance_framework,
        current_retention_days=vin.primary_retention_days,
        immutability_enabled=vin.immutability_enabled,
        encryption_enabled=True,
        offsite_copy_enabled=False,
        target_rpo_hours=vin.target_rpo_hours,
    )
    design.compliance = check_compliance(comp_in)

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
