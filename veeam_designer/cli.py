import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ._version import __version__
from .agent import size_agent
from .config import CONFIG, select_profile
from .interactive import collect_inputs_interactive, print_human_summary
from .models import AgentInput, NasInput, ReplicationInput, VeeamInput
from .nas import size_nas
from .parser import load_project
from .replication import size_replication
from .service import design_payload_from_input
from .sizing import design_multi_site, design_veeam_environment


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""

    p = argparse.ArgumentParser(
        prog="veeam-designer",
        description="Plan and size Veeam backup environments.",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    p.add_argument(
        "--workload-type",
        choices=["vm", "nas", "physical", "replication"],
        default="vm",
        help="Workload type to size (default: vm)",
    )
    p.add_argument("--profile", help="Profile name from profiles.json", default=None)
    p.add_argument("--project-file", help="JSON or YAML project definition file")

    # --- VM / common flags ---
    p.add_argument("--total-data-tb", type=float)
    p.add_argument("--annual-growth-percent", type=float, default=0.0)
    p.add_argument("--daily-change-percent", type=float)
    p.add_argument("--backup-type", default="synthetic_full_weekly")
    p.add_argument("--primary-retention-days", type=int, default=30)
    p.add_argument("--gfs-weekly-count", type=int, default=4)
    p.add_argument("--gfs-monthly-count", type=int, default=12)
    p.add_argument("--gfs-yearly-count", type=int, default=3)
    p.add_argument("--backup-window-hours", type=float, default=8.0)
    p.add_argument("--target-rpo-hours", type=float, default=24.0)
    p.add_argument("--compression-ratio", type=float)
    p.add_argument("--dedupe-ratio", type=float)
    p.add_argument("--throughput-mb-per-core", type=float)
    p.add_argument("--vm-count", type=int, default=0)
    p.add_argument("--avg-vm-size-gb", type=float, default=0.0)
    p.add_argument("--wan-bandwidth-mbps", type=float, default=0.0)
    p.add_argument("--repo-type", default="sobr")
    p.add_argument("--hypervisor", default="vmware")
    p.add_argument("--has-san-access", action="store_true")
    p.add_argument("--on-host-proxy", action="store_true")
    # Round 2
    p.add_argument("--workload-count", type=int, default=0)
    p.add_argument("--concurrent-jobs", type=int, default=5)
    p.add_argument("--indexing", action="store_true")
    p.add_argument("--no-v13-appliance", action="store_true")
    # Round 3
    p.add_argument("--no-refs-xfs", action="store_true")
    p.add_argument("--immutability", action="store_true")
    p.add_argument("--block-generation-days", type=int, default=10)
    # Round 5
    p.add_argument("--capacity-tier", action="store_true")
    p.add_argument("--capacity-tier-fraction", type=float, default=0.5)
    p.add_argument("--direct-to-object", action="store_true")
    p.add_argument("--capacity-tier-immutable", action="store_true")

    # --- NAS flags ---
    p.add_argument("--nas-source-tb", type=float)
    p.add_argument("--nas-share-count", type=int, default=70)
    p.add_argument("--nas-file-count-millions", type=float, default=1.0)
    p.add_argument("--nas-daily-change-pct", type=float, default=5.0)
    p.add_argument("--nas-retention-days", type=int, default=14)
    p.add_argument("--nas-compress-pct", type=float, default=30.0)
    p.add_argument("--nas-cft", action="store_true")

    # --- Physical / Agent flags ---
    p.add_argument("--machine-count", type=int, default=0)
    p.add_argument("--avg-machine-size-gb", type=float, default=500.0)
    p.add_argument("--agent-daily-change-pct", type=float, default=5.0)
    p.add_argument("--agent-retention-days", type=int, default=14)
    p.add_argument("--agent-os-type", default="windows")
    p.add_argument("--agent-network-mbps", type=float, default=1000.0)

    # --- Replication flags ---
    p.add_argument("--rep-source-tb", type=float)
    p.add_argument("--rep-vm-count", type=int, default=0)
    p.add_argument("--rep-wan-mbps", type=float, default=0.0)
    p.add_argument("--rep-rpo-hours", type=float, default=1.0)
    p.add_argument("--cdp", action="store_true")
    p.add_argument("--cdp-rpo-seconds", type=int, default=15)

    p.add_argument("--json", action="store_true", help="Output JSON")

    return p


def _print_nas_summary(design):
    print("\n=== NAS Sizing ===")
    print(f"  Cache repo  : {design.cache_repo_tb:.2f} TB")
    print(f"  Primary repo: {design.primary_repo_tb:.1f} TB")
    print(f"  GFS repo    : {design.gfs_repo_tb:.1f} TB")
    print(f"  Total repo  : {design.total_repo_tb:.1f} TB")
    print(f"  File proxies: {design.file_proxy_cores} cores, {design.file_proxy_ram_gb} GB RAM")
    for note in design.notes:
        print(f"  NOTE: {note}")


def _print_agent_summary(design):
    print("\n=== Agent / Physical Sizing ===")
    print(f"  Total repo      : {design.total_repo_tb:.1f} TB")
    print(
        f"  Coordinator     : {design.coordinator_cores} cores, {design.coordinator_ram_gb} GB RAM"
    )
    for note in design.notes:
        print(f"  NOTE: {note}")


def _print_replication_summary(design):
    print("\n=== Replication Sizing ===")
    print(f"  Required bandwidth : {design.required_mbps:.1f} Mbps")
    print(f"  Meets RPO          : {'YES' if design.meets_rpo else 'NO'}")
    print(f"  Replica storage    : {design.replica_storage_tb:.1f} TB")
    if design.cdp_proxy_cores:
        print(f"  CDP proxy cores    : {design.cdp_proxy_cores}")
        print(f"  CDP journal        : {design.cdp_journal_tb:.2f} TB")
    for note in design.notes:
        print(f"  NOTE: {note}")


def _roles_dict(roles):
    return {
        "backup_server": asdict(roles.backup_server),
        "proxies": asdict(roles.proxies),
        "hardened_repos": asdict(roles.hardened_repos) if roles.hardened_repos else None,
        "gateways": asdict(roles.gateways) if roles.gateways else None,
    }


def main():
    parser = build_parser()
    args = parser.parse_args()
    select_profile(args.profile)

    if args.project_file:
        obj = load_project(Path(args.project_file))
        if isinstance(obj, list):
            # Multi-site VM design
            if args.json:
                print(json.dumps(design_payload_from_input(obj), indent=2))
            else:
                multi = design_multi_site(obj)
                print(f"Total repo across sites: {multi.total_repo_tb:.1f} TB")
                for s in multi.sites:
                    print(
                        f"- {s.name}: {s.design.repo.total_repo_tb:.1f} TB total repo, "
                        f"{s.design.roles.proxies.proxy_count} proxies"
                    )
            return

        # Single-object project file — dispatch by type
        if isinstance(obj, NasInput):
            design = size_nas(obj)
            if args.json:
                print(json.dumps(design_payload_from_input(obj), indent=2))
            else:
                _print_nas_summary(design)
            return

        if isinstance(obj, AgentInput):
            design = size_agent(obj)
            if args.json:
                print(json.dumps(design_payload_from_input(obj), indent=2))
            else:
                _print_agent_summary(design)
            return

        if isinstance(obj, ReplicationInput):
            design = size_replication(obj)
            if args.json:
                print(json.dumps(design_payload_from_input(obj), indent=2))
            else:
                _print_replication_summary(design)
            return

        # VeeamInput (VM workload)
        vin = obj

    else:
        workload_type = args.workload_type

        if workload_type == "nas":
            if args.nas_source_tb is None:
                parser.error("--nas-source-tb is required for --workload-type nas")
            nin = NasInput(
                source_tb=args.nas_source_tb,
                share_count=args.nas_share_count,
                file_count_millions=args.nas_file_count_millions,
                daily_change_pct=args.nas_daily_change_pct,
                backup_window_hours=args.backup_window_hours,
                retention_days=args.nas_retention_days,
                compress_pct=args.nas_compress_pct,
                storage_native_cft=args.nas_cft,
            )
            design = size_nas(nin)
            if args.json:
                print(json.dumps(design_payload_from_input(nin), indent=2))
            else:
                _print_nas_summary(design)
            return

        if workload_type == "physical":
            if args.machine_count == 0:
                parser.error("--machine-count is required for --workload-type physical")
            ain = AgentInput(
                machine_count=args.machine_count,
                avg_size_gb=args.avg_machine_size_gb,
                daily_change_pct=args.agent_daily_change_pct,
                backup_window_hours=args.backup_window_hours,
                retention_days=args.agent_retention_days,
                os_type=args.agent_os_type,
                network_bandwidth_mbps=args.agent_network_mbps,
            )
            design = size_agent(ain)
            if args.json:
                print(json.dumps(design_payload_from_input(ain), indent=2))
            else:
                _print_agent_summary(design)
            return

        if workload_type == "replication":
            if args.rep_source_tb is None:
                parser.error("--rep-source-tb is required for --workload-type replication")
            rin = ReplicationInput(
                source_tb=args.rep_source_tb,
                vm_count=args.rep_vm_count,
                wan_mbps=args.rep_wan_mbps,
                rpo_hours=args.rep_rpo_hours,
                cdp_enabled=args.cdp,
                rpo_seconds=args.cdp_rpo_seconds,
            )
            design = size_replication(rin)
            if args.json:
                print(json.dumps(design_payload_from_input(rin), indent=2))
            else:
                _print_replication_summary(design)
            return

        # VM workload (default)
        if args.total_data_tb is None or args.daily_change_percent is None:
            vin = collect_inputs_interactive()
        else:
            vin = VeeamInput(
                total_data_tb=args.total_data_tb,
                annual_growth_percent=args.annual_growth_percent,
                daily_change_percent=args.daily_change_percent,
                backup_type=args.backup_type,
                primary_retention_days=args.primary_retention_days,
                gfs_weekly_count=args.gfs_weekly_count,
                gfs_monthly_count=args.gfs_monthly_count,
                gfs_yearly_count=args.gfs_yearly_count,
                backup_window_hours=args.backup_window_hours,
                target_rpo_hours=args.target_rpo_hours,
                compression_ratio=args.compression_ratio or CONFIG["compression_ratio_default"],
                dedupe_ratio=args.dedupe_ratio or CONFIG["dedupe_ratio_default"],
                throughput_mb_per_core=args.throughput_mb_per_core
                or CONFIG["throughput_mb_per_core"],
                vm_count=args.vm_count,
                avg_vm_size_gb=args.avg_vm_size_gb,
                wan_bandwidth_mbps=args.wan_bandwidth_mbps,
                repo_type=args.repo_type,
                hypervisor=args.hypervisor,
                has_san_access=args.has_san_access,
                on_host_proxy=args.on_host_proxy,
                workload_count=args.workload_count,
                concurrent_jobs=args.concurrent_jobs,
                indexing_enabled=args.indexing,
                v13_appliance=not args.no_v13_appliance,
                refs_xfs=not args.no_refs_xfs,
                immutability_enabled=args.immutability,
                block_generation_days=args.block_generation_days,
                capacity_tier_enabled=args.capacity_tier,
                capacity_tier_fraction=args.capacity_tier_fraction,
                direct_to_object=args.direct_to_object,
                capacity_tier_immutable=args.capacity_tier_immutable,
            )

    design = design_veeam_environment(vin)

    if args.json:
        print(json.dumps(design_payload_from_input(vin), indent=2))
    else:
        print_human_summary(design)


if __name__ == "__main__":
    main()
