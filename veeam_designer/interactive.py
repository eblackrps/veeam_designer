from __future__ import annotations

from .config import CONFIG
from .models import VeeamDesign, VeeamInput
from .sizing import design_veeam_environment  # noqa: F401


def _prompt_float(prompt: str, default: float) -> float:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("Invalid number, using default.")
        return default


def _prompt_int(prompt: str, default: int) -> int:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("Invalid integer, using default.")
        return default


def _prompt_str(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def _prompt_bool(prompt: str, default: bool = False) -> bool:
    default_text = "yes" if default else "no"
    raw = input(f"{prompt} (yes/no) [{default_text}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "true", "1"}


def collect_inputs_interactive() -> VeeamInput:
    print("=== Veeam Environment Input Wizard ===")
    print("Press ENTER to accept defaults. Ctrl+C to bail.\n")

    # Special-case total_data_tb so we can detect if user overrode it
    total_default = 100.0
    raw_total = input(f"Total protected data (TB) [{total_default}]: ").strip()
    if raw_total:
        try:
            total_data_tb = float(raw_total)
            total_overridden = True
        except ValueError:
            print("Invalid number, using default.")
            total_data_tb = total_default
            total_overridden = False
    else:
        total_data_tb = total_default
        total_overridden = False

    annual_growth_percent = _prompt_float("Annual growth (%)", 5.0)
    years_to_plan_for = _prompt_int(
        "Capacity growth forecast horizon (years)", int(CONFIG["years_to_plan_for"])
    )
    daily_change_percent = _prompt_float("Average daily change (%)", 5.0)

    backup_type = _prompt_str(
        "Backup type (synthetic_full_weekly / forever_forward / active_full_weekly)",
        "synthetic_full_weekly",
    )

    primary_retention_days = _prompt_int("Primary backup retention (days)", 14)
    gfs_weekly_count = _prompt_int("GFS weekly restore points", 0)
    gfs_monthly_count = _prompt_int("GFS monthly restore points", 0)
    gfs_yearly_count = _prompt_int("GFS yearly restore points", 0)

    backup_window_hours = _prompt_float("Primary backup window (hours)", 8.0)
    target_rpo_hours = _prompt_float("Target RPO (hours)", 24.0)

    compression_ratio = _prompt_float(
        "Compression ratio (effective, higher = better)",
        CONFIG["compression_ratio_default"],
    )
    dedupe_ratio = _prompt_float(
        "Dedupe ratio (effective, higher = better)",
        CONFIG["dedupe_ratio_default"],
    )
    throughput_mb_per_core = _prompt_float(
        "Custom proxy throughput override (MB/s per core, 0 = auto)", 0.0
    )

    vm_count = _prompt_int("Approximate VM count", 100)
    avg_vm_size_gb = _prompt_float("Average VM size (GB)", 100.0)

    # If user did NOT override total_data_tb and we have VM info, infer total TB from VMs
    if not total_overridden and vm_count > 0 and avg_vm_size_gb > 0:
        inferred_total_tb = (vm_count * avg_vm_size_gb) / 1024.0
        total_data_tb = round(inferred_total_tb, 2)

    wan_bandwidth_mbps = _prompt_float("WAN bandwidth for copy/replication (Mbps, 0 = none)", 500.0)
    wan_accel_mode = _prompt_str(
        "WAN accelerator mode (auto / direct / low / high)", "auto"
    ).lower()
    repo_type = _prompt_str("Repo type (local_disk / san / sobr / object)", "sobr").lower()

    immutability_enabled = _prompt_bool("Enable immutability", False)
    immutability_days = _prompt_int("Immutability period (days)", 30) if immutability_enabled else 0
    block_generation_days = (
        _prompt_int("Object block generation planning days", 10)
        if immutability_enabled and repo_type == "object"
        else 10
    )

    capacity_tier_enabled = False
    capacity_tier_fraction = 0.5
    capacity_tier_policy = "move"
    capacity_tier_immutable = False
    if repo_type == "sobr":
        capacity_tier_enabled = _prompt_bool("Enable SOBR capacity tier", False)
        if capacity_tier_enabled:
            capacity_tier_policy = _prompt_str(
                "Capacity tier policy (move / copy / copy_move)", "move"
            ).lower()
            if capacity_tier_policy in {"move", "copy_move"}:
                move_percent = _prompt_float("Modeled move fraction (%)", 50.0)
                capacity_tier_fraction = max(0.0, min(100.0, move_percent)) / 100.0
            capacity_tier_immutable = _prompt_bool("Enable object lock on capacity tier", False)

    object_cost_usd_per_tb_month = _prompt_float(
        "Object storage planning rate ($/TB/month)",
        float(CONFIG["object_cost_usd_per_tb_month"]),
    )
    onprem_cost_usd_per_tb_year = _prompt_float(
        "Local storage planning rate ($/TB/year)",
        float(CONFIG["onprem_cost_usd_per_tb_year"]),
    )

    hypervisor = _prompt_str(
        "Hypervisor (vmware / hyperv / nutanix_ahv / proxmox / agent)", "vmware"
    )
    deployment_mode = _prompt_str(
        "Backup server deployment (software_appliance / windows)", "software_appliance"
    )

    proxy_deployment_mode = "managed_os"
    if hypervisor.lower() == "vmware":
        proxy_deployment_mode = _prompt_str(
            "VMware proxy deployment (managed_os / infrastructure_appliance)", "managed_os"
        )

    platform_host_count = 0
    platform_cluster_count = 1
    platform_concurrent_tasks = 0
    worker_task_limit = 4
    if hypervisor.lower() in {"nutanix_ahv", "ahv", "proxmox", "proxmox_ve", "pve"}:
        platform_host_count = _prompt_int("Platform host count", 3)
        platform_cluster_count = _prompt_int("Platform cluster count", 1)
        platform_concurrent_tasks = _prompt_int("Desired concurrent worker tasks", 8)
        worker_task_limit = _prompt_int("Maximum tasks per worker", 4)

    # Transport selection (replaces the bad On-host/HotAdd yes/no)
    transport_default = CONFIG.get("proxy_transport_default", "auto")
    transport_mode = _prompt_str(
        "Proxy transport mode (auto / san / hotadd / nbd)", transport_default
    ).lower()

    # Map transport_mode -> has_san_access / on_host_proxy
    if transport_mode == "san":
        has_san_access = True
        on_host_proxy = False
    elif transport_mode == "hotadd":
        has_san_access = False
        on_host_proxy = True
    elif transport_mode == "nbd":
        has_san_access = False
        on_host_proxy = False
    else:  # auto or unknown -> leave both False, let Veeam decide
        has_san_access = False
        on_host_proxy = False

    return VeeamInput(
        total_data_tb=total_data_tb,
        annual_growth_percent=annual_growth_percent,
        years_to_plan_for=years_to_plan_for,
        daily_change_percent=daily_change_percent,
        backup_type=backup_type,
        primary_retention_days=primary_retention_days,
        gfs_weekly_count=gfs_weekly_count,
        gfs_monthly_count=gfs_monthly_count,
        gfs_yearly_count=gfs_yearly_count,
        backup_window_hours=backup_window_hours,
        target_rpo_hours=target_rpo_hours,
        compression_ratio=compression_ratio,
        dedupe_ratio=dedupe_ratio,
        throughput_mb_per_core=throughput_mb_per_core,
        vm_count=vm_count,
        avg_vm_size_gb=avg_vm_size_gb,
        wan_bandwidth_mbps=wan_bandwidth_mbps,
        wan_accel_mode=wan_accel_mode,
        repo_type=repo_type,
        hypervisor=hypervisor,
        has_san_access=has_san_access,
        on_host_proxy=on_host_proxy,
        deployment_mode=deployment_mode,
        proxy_deployment_mode=proxy_deployment_mode,
        platform_host_count=platform_host_count,
        platform_cluster_count=platform_cluster_count,
        platform_concurrent_tasks=platform_concurrent_tasks,
        worker_task_limit=worker_task_limit,
        immutability_enabled=immutability_enabled,
        immutability_days=immutability_days,
        block_generation_days=block_generation_days,
        capacity_tier_enabled=capacity_tier_enabled,
        capacity_tier_fraction=capacity_tier_fraction,
        capacity_tier_policy=capacity_tier_policy,
        capacity_tier_immutable=capacity_tier_immutable,
        direct_to_object=repo_type == "object",
        object_cost_usd_per_tb_month=object_cost_usd_per_tb_month,
        onprem_cost_usd_per_tb_year=onprem_cost_usd_per_tb_year,
    )


def print_human_summary(d: VeeamDesign) -> None:
    print("\n=== Veeam Design Summary ===\n")

    print("Repository sizing:")
    print(f"  Primary repo capacity : {d.repo.primary_repo_tb:.1f} TB")
    print(f"  GFS repo capacity     : {d.repo.gfs_repo_tb:.1f} TB")
    print(f"  Total repo capacity   : {d.repo.total_repo_tb:.1f} TB\n")

    print("Roles:")
    print(
        f"  Backup server         : {d.roles.backup_server.cores} vCPU, "
        f"{d.roles.backup_server.ram_gb} GB RAM"
    )
    if d.roles.platform_workers:
        workers = d.roles.platform_workers
        print(
            f"  {workers.platform.upper()} workers      : {workers.worker_count}x, "
            f"{workers.cores_per_worker} vCPU / {workers.ram_gb_per_worker} GB RAM / "
            f"{workers.disk_gb_per_worker} GB disk each "
            f"({workers.total_concurrent_tasks} total tasks)"
        )
    else:
        print(
            f"  Proxies               : {d.roles.proxies.proxy_count}x, "
            f"{d.roles.proxies.cores_per_proxy} cores each "
            f"({d.roles.proxies.total_proxy_cores} total cores, "
            f"{d.roles.proxies.total_parallel_tasks} total tasks, "
            f"{d.roles.proxies.estimated_capacity_mb_s:.1f} MB/s effective)"
        )
    if d.roles.hardened_repos:
        print(
            f"  Hardened repo hosts   : {d.roles.hardened_repos.count} "
            f"(~{d.roles.hardened_repos.tb_per_host:.1f} TB, "
            f"{d.roles.hardened_repos.cpu_cores_each} cores, "
            f"{d.roles.hardened_repos.ram_gb_each} GB each)"
        )
    if d.roles.gateways:
        print(
            f"  Gateway servers       : {d.roles.gateways.count}x "
            f"({d.roles.gateways.cores_each} cores, "
            f"{d.roles.gateways.ram_gb_each} GB each)"
        )
    print("")

    print("SOBR:")
    print(
        f"  Extents               : {d.sobr.extent_count} "
        f"(~{d.sobr.extent_size_tb:.1f} TB each), "
        f"capacity tier ~{d.sobr.capacity_tier_tb:.1f} TB"
    )
    print("")

    print("Jobs:")
    print(f"  Total jobs            : {len(d.jobs.jobs)}")
    for job in d.jobs.jobs:
        print(
            f"    {job.name}: {job.vm_count} VMs, {job.total_tb:.2f} TB, "
            f"mode={job.mode}, repo={job.repo_target}"
        )
    print("")

    print("Network:")
    print(f"  Required WAN          : {d.network.required_mbps:.1f} Mbps")
    print(
        f"  Achievable RPO        : {d.network.achievable_rpo_hours:.1f} h "
        f"(target {d.input.target_rpo_hours:.1f} h)"
    )
    print(f"  Meets target          : {d.network.meets_target}\n")

    print("Cost planning assumptions:")
    print(f"  Monthly object        : ${d.cost.monthly_object_usd:.2f}")
    print(f"  Yearly object         : ${d.cost.yearly_object_usd:.2f}")
    print(f"  Yearly on-prem        : ${d.cost.yearly_onprem_usd:.2f}")
    print(f"  Total storage plan    : ${d.cost.total_yearly_usd:.2f}\n")

    print("Risk:")
    print(f"  Overall               : {d.risk.level.upper()} (score {d.risk.total_score})")
    for k, v in d.risk.details.items():
        print(f"    {k}: {v}")
    print("")

    if d.notes:
        print("Notes / recommendations:")
        for _, note in d.notes.items():
            print(f"  - {note}")
        print("")

    print("Blueprint:")
    for note in d.blueprint.notes:
        print(f"  - {note}")
    print("")
