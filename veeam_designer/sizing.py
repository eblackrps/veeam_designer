from typing import Dict, List

from .blueprint import build_blueprint
from .compliance import check_compliance
from .config import CONFIG
from .cost import estimate_costs
from .jobs import build_jobs
from .licensing import estimate_license
from .models import (
    ComplianceInput,
    LicenseInput,
    MultiSiteDesign,
    RepoSizing,
    RiskScore,
    SiteDesign,
    VeeamDesign,
    VeeamInput,
    VeeamOneInput,
    WanAccelInput,
)
from .nas import size_nas
from .network import build_network_plan
from .orca import size_orca
from .replication import size_replication
from .repo_perf import estimate_repo_perf
from .risk import compute_risk
from .roles import build_role_plan
from .sobr import design_sobr
from .tape import size_tape
from .veeam_one import size_veeam_one
from .wan_accel import size_wan_accel
from .workload_math import projected_daily_change_tb, projected_total_data_tb


def size_repository(vin: VeeamInput) -> RepoSizing:
    """Size provisioned repository capacity from the selected Veeam backup-chain model."""

    effective_total_tb = projected_total_data_tb(
        total_data_tb=vin.total_data_tb,
        annual_growth_percent=vin.annual_growth_percent,
        years_to_plan_for=vin.years_to_plan_for,
    )
    daily_change_size_tb = projected_daily_change_tb(
        total_data_tb=vin.total_data_tb,
        daily_change_percent=vin.daily_change_percent,
        annual_growth_percent=vin.annual_growth_percent,
        years_to_plan_for=vin.years_to_plan_for,
    )

    reduction_ratio = max(0.01, vin.compression_ratio * vin.dedupe_ratio)
    full_physical_tb = effective_total_tb / reduction_ratio
    incremental_physical_tb = daily_change_size_tb / reduction_ratio

    retention_days = max(0, int(vin.primary_retention_days))
    if vin.immutability_enabled:
        configured_lock_days = (
            vin.immutability_days if vin.immutability_days > 0 else retention_days
        )
        retention_days = max(retention_days, configured_lock_days)

    # VBR v13 daily retention retains N+1 days and never fewer than three restore points.
    restore_points = max(3, retention_days + 1)
    backup_type = (vin.backup_type or "synthetic_full_weekly").strip().lower()
    notes: list[str] = []

    if backup_type == "forever_forward_incremental":
        chain_tb = full_physical_tb + incremental_physical_tb * (restore_points - 1)
        calculation_basis = (
            f"Forever-forward incremental: 1 full + {restore_points - 1} incremental "
            f"restore points ({restore_points} total)."
        )
    elif backup_type == "reverse_incremental":
        chain_tb = full_physical_tb + incremental_physical_tb * (restore_points - 1)
        calculation_basis = (
            f"Reverse incremental: latest full + {restore_points - 1} rollback points "
            f"({restore_points} total)."
        )
        notes.append(
            "Reverse incremental is deprecated in Veeam Backup & Replication v13. "
            "The capacity model covers the retained full/rollback chain; operational free-space "
            "reserve is applied separately."
        )
    else:
        # Forward incremental with a weekly synthetic full. On Fast Clone repositories, Veeam
        # recommends treating physical capacity similarly to forever-forward because cloned fulls
        # reuse blocks. Without Fast Clone, retention is enforced per chain and a weekly schedule
        # can temporarily retain up to six restore points beyond the requested daily window.
        if vin.refs_xfs:
            chain_tb = full_physical_tb + incremental_physical_tb * (restore_points - 1)
            calculation_basis = (
                f"Weekly synthetic full with Fast Clone: physical chain modeled as 1 full + "
                f"{restore_points - 1} changed-data restore points."
            )
            notes.append(
                "ReFS/XFS Fast Clone prevents synthetic fulls from consuming another complete "
                "physical full. Actual block reuse depends on workload change locality."
            )
        else:
            peak_restore_points = restore_points + 6
            full_count = math.ceil(peak_restore_points / 7)
            incremental_count = peak_restore_points - full_count
            chain_tb = (
                full_physical_tb * full_count
                + incremental_physical_tb * incremental_count
            )
            calculation_basis = (
                f"Weekly synthetic full without Fast Clone: conservative chain peak of "
                f"{peak_restore_points} restore points ({full_count} full, "
                f"{incremental_count} incremental)."
            )
            notes.append(
                "Forward-incremental retention is enforced per backup chain. With weekly fulls, "
                "an older chain can remain until the newer chain satisfies retention; the "
                "calculator allows up to six extra daily restore points at the chain boundary."
            )

    reserve_factor = max(1.0, float(CONFIG.get("repo_overhead_factor", 1.0)))
    primary_repo_tb = chain_tb * reserve_factor
    if reserve_factor > 1.0:
        notes.append(
            f"Provisioned primary capacity includes a configured operational reserve of "
            f"{(reserve_factor - 1.0) * 100:.0f}% for merge/transform workspace and variance."
        )

    gfs_count = max(0, vin.gfs_weekly_count) + max(0, vin.gfs_monthly_count) + max(
        0, vin.gfs_yearly_count
    )
    if gfs_count:
        # Exact Fast Clone physical usage for long-term points depends on block churn and cannot
        # be known from retention counts alone. Use a full-equivalent upper bound rather than an
        # unsupported dedupe multiplier.
        gfs_repo_tb = gfs_count * full_physical_tb
        notes.append(
            f"GFS capacity is reported as a conservative full-equivalent upper bound for "
            f"{gfs_count} retained GFS points. Fast Clone can materially reduce actual physical "
            "usage, but exact savings require block-level change history."
        )
    else:
        gfs_repo_tb = 0.0

    total_repo_tb = primary_repo_tb + gfs_repo_tb

    if vin.immutability_enabled:
        notes.append(
            f"Immutability is modeled by extending the effective short-term retention window "
            f"to {retention_days} day(s); no arbitrary metadata percentage is added."
        )

    return RepoSizing(
        primary_repo_tb=round(primary_repo_tb, 1),
        gfs_repo_tb=round(gfs_repo_tb, 1),
        total_repo_tb=round(total_repo_tb, 1),
        calculation_basis=calculation_basis,
        notes=notes,
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
        notes["wan"] = (
            "WAN bandwidth cannot carry the projected changed data inside the configured transfer window."
        )

    if vin.vm_count and roles.proxies.total_parallel_tasks < vin.vm_count / 10:
        if roles.platform_workers:
            notes["data_movers"] = (
                "Worker parallelism is low vs VM count. Review worker count or concurrent-task "
                "limits for the selected platform."
            )
        else:
            notes["data_movers"] = (
                "Proxy parallelism is low vs VM count. Consider more proxy cores or additional "
                "proxy servers."
            )

    hv = vin.hypervisor.lower()
    if hv == "vmware":
        notes.setdefault(
            "platform",
            "VMware: align proxies with clusters, prefer DirectSAN or HotAdd where possible, "
            "and avoid NBD for large/high-churn workloads unless absolutely necessary.",
        )
    elif hv in {"hyperv", "hyper-v"}:
        notes.setdefault(
            "platform",
            "Hyper-V: prefer off-host proxies with SAN access for larger environments. "
            "Ensure Cluster Shared Volumes are visible to off-host proxies and coordinate "
            "VSS load on busy hosts.",
        )
    elif hv in {"nutanix_ahv", "ahv"}:
        notes.setdefault(
            "platform",
            "Nutanix AHV: deploy workers in each AHV cluster, size worker task limits for the "
            "desired parallelism, and keep the configured worker count at or below host count.",
        )
    elif hv in {"proxmox", "proxmox_ve", "pve"}:
        notes.setdefault(
            "platform",
            "Proxmox VE: worker tasks are per VM. Same-host workers can use Hot-Add; when a worker "
            "is not present on the source host, processing can use NBD across the Proxmox network.",
        )
    elif hv == "agent":
        notes.setdefault(
            "platform",
            "Agent-based backups: treat these as network/volume workloads. "
            "Plan for higher overhead, longer windows, and ensure backup traffic is "
            "segmented from production where possible.",
        )

    # Object First sizing is opt-in. Generic object storage must not be treated as Ootbi.
    orca = None
    if vin.repo_type == "object" and vin.object_storage_provider.lower() == "objectfirst":
        orca = size_orca(
            total_protected_tb=repo.total_repo_tb,
            node_capacity_tb=vin.objectfirst_node_tb,
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
            source_tb=projected_total_data_tb(
                total_data_tb=vin.total_data_tb,
                annual_growth_percent=vin.annual_growth_percent,
                years_to_plan_for=vin.years_to_plan_for,
            ),
            wan_mbps=vin.wan_bandwidth_mbps,
            dedupe_ratio=vin.dedupe_ratio,
            compression_ratio=vin.compression_ratio,
            daily_change_pct=vin.daily_change_percent,
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
        risk=RiskScore(total_score=0, level="green", details={}),
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
