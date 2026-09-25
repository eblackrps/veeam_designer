from math import ceil
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
    """Size repository capacity from retention, chain type, and documented Veeam behavior."""

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

    backup_type = (vin.backup_type or "synthetic_full_weekly").strip().lower()
    aliases = {
        "forever_forward": "forever_forward_incremental",
        "active_full": "active_full_weekly",
    }
    backup_type = aliases.get(backup_type, backup_type)
    supported_types = {
        "forever_forward_incremental",
        "synthetic_full_weekly",
        "active_full_weekly",
        "reverse_incremental",
    }
    if backup_type not in supported_types:
        raise ValueError(f"Unsupported backup type: {vin.backup_type!r}")

    if (
        vin.immutability_enabled
        and vin.repo_type != "object"
        and backup_type in {"forever_forward_incremental", "reverse_incremental"}
    ):
        raise ValueError(
            "Veeam hardened repositories with immutability require forward incremental "
            "backup chains with scheduled active or synthetic full backups."
        )

    retention_days = max(0, int(vin.primary_retention_days))
    effective_retention_days = retention_days
    notes: list[str] = [
        "Daily retention assumes one successful restore point per day. VBR 13 retains N+1 days "
        "with a minimum of three restore points."
    ]

    if vin.immutability_enabled:
        immutability_days = max(0, int(vin.immutability_days))
        if immutability_days > 0:
            immutable_window_days = immutability_days
            if vin.repo_type == "object":
                block_generation_days = max(0, int(vin.block_generation_days))
                immutable_window_days += block_generation_days
                notes.append(
                    "Object-storage immutability includes the block-generation planning "
                    f"assumption ({block_generation_days} day(s)). Veeam applies block generation "
                    "automatically; the actual period depends on the object-storage provider."
                )
            effective_retention_days = max(retention_days, immutable_window_days)
            notes.append(
                f"Immutability extends the effective short-term retention window to "
                f"{effective_retention_days} day(s); no arbitrary metadata percentage is added."
            )
        else:
            notes.append(
                "Immutability is enabled but no immutability duration is supplied. Capacity is "
                "not inflated by an invented percentage; enter the lock period to model its effect."
            )

    daily_restore_points = max(3, effective_retention_days + 1)
    weekly_chain_days = 7
    max_forward_points = daily_restore_points + (weekly_chain_days - 1)

    if backup_type == "forever_forward_incremental":
        retained_data_tb = full_physical_tb + incremental_physical_tb * (daily_restore_points - 1)
        calculation_basis = (
            f"Forever-forward incremental: 1 full + {daily_restore_points - 1} incremental "
            f"restore points ({daily_restore_points} retained points)."
        )
    elif backup_type == "reverse_incremental":
        retained_data_tb = full_physical_tb + incremental_physical_tb * (daily_restore_points - 1)
        calculation_basis = (
            f"Reverse incremental: latest full + {daily_restore_points - 1} rollback points "
            f"({daily_restore_points} retained points)."
        )
        notes.append(
            "Reverse incremental is deprecated in VBR 13 and is not valid on an immutable "
            "hardened repository."
        )
    else:
        full_count = ceil(max_forward_points / weekly_chain_days)
        incremental_count = max_forward_points - full_count
        if backup_type == "synthetic_full_weekly" and vin.refs_xfs and vin.repo_type != "object":
            retained_data_tb = full_physical_tb + incremental_physical_tb * (max_forward_points - 1)
            calculation_basis = (
                "Weekly synthetic full with Fast Clone: forward-incremental chain overlap "
                f"allows up to {max_forward_points} restore points; physical data is modeled "
                "as one full plus changed blocks for the remaining points."
            )
            notes.append(
                "Fast Clone reuses existing blocks for synthetic fulls. Exact physical savings "
                "depend on block-change locality, so this changed-block model is a planning estimate."
            )
        else:
            retained_data_tb = (
                full_physical_tb * full_count + incremental_physical_tb * incremental_count
            )
            full_kind = "active full" if backup_type == "active_full_weekly" else "synthetic full"
            calculation_basis = (
                f"Weekly {full_kind} without Fast Clone savings: forward-incremental retention "
                f"can peak at {max_forward_points} restore points "
                f"({full_count} full, {incremental_count} incremental)."
            )

    operational_headroom_tb = 0.0
    if vin.repo_type != "object":
        transformation_factor = max(0.0, float(CONFIG.get("repo_overhead_factor", 1.25)))
        operational_headroom_tb = full_physical_tb * transformation_factor
        notes.append(
            "Disk-repository operational headroom reserves at least one full backup x "
            f"{transformation_factor:.2f} for backup-chain transformation. One-off full-backup "
            "headroom is a separate planning consideration because Veeam does not publish one "
            "universal quantity for it."
        )

    primary_repo_tb = retained_data_tb + operational_headroom_tb

    gfs_count = (
        max(0, vin.gfs_weekly_count) + max(0, vin.gfs_monthly_count) + max(0, vin.gfs_yearly_count)
    )
    if backup_type == "reverse_incremental" and gfs_count:
        gfs_repo_tb = 0.0
        notes.append(
            "GFS is not modeled for reverse incremental because that combination is unsupported."
        )
    elif gfs_count:
        gfs_repo_tb = gfs_count * full_physical_tb
        notes.append(
            f"GFS is sized as a conservative full-equivalent upper bound for {gfs_count} point(s). "
            "Fast Clone can reduce physical usage, but exact savings require block-level history."
        )
    else:
        gfs_repo_tb = 0.0

    total_repo_tb = primary_repo_tb + gfs_repo_tb

    return RepoSizing(
        primary_repo_tb=round(primary_repo_tb, 1),
        gfs_repo_tb=round(gfs_repo_tb, 1),
        total_repo_tb=round(total_repo_tb, 1),
        short_term_data_tb=round(retained_data_tb, 1),
        operational_headroom_tb=round(operational_headroom_tb, 1),
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
            "WAN bandwidth does not meet target RPO; replication/copy jobs will lag behind."
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
            source_tb=projected_total_data_tb(
                total_data_tb=vin.total_data_tb,
                annual_growth_percent=vin.annual_growth_percent,
                years_to_plan_for=vin.years_to_plan_for,
            ),
            wan_mbps=vin.wan_bandwidth_mbps,
            dedupe_ratio=1.0,
            compression_ratio=1.0,
            daily_change_pct=vin.daily_change_percent,
            mode=vin.wan_accel_mode,
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
