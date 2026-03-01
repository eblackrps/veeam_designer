import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import List, Tuple

from .models import VeeamInput
from .sizing import design_veeam_environment, design_multi_site
from .config import select_profile, CONFIG
from .parser import load_project
from .interactive import collect_inputs_interactive, print_human_summary


def parse_args():
    p = argparse.ArgumentParser(description="Veeam environment architect (final CLI)")

    p.add_argument("--profile", help="Profile name from profiles.json", default=None)
    p.add_argument("--project-file", help="JSON or YAML project definition file")

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

    p.add_argument("--json", action="store_true", help="Output JSON")

    return p.parse_args()


def main():
    args = parse_args()
    select_profile(args.profile)

    if args.project_file:
        obj = load_project(Path(args.project_file))
        if isinstance(obj, list):
            sites: List[Tuple[str, VeeamInput]] = obj
            multi = design_multi_site(sites)
            if args.json:
                payload = {
                    "total_repo_tb": multi.total_repo_tb,
                    "notes": multi.notes,
                    "sites": [
                        {
                            "name": s.name,
                            "design": {
                                "input": asdict(s.design.input),
                                "repo": asdict(s.design.repo),
                                "roles": {
                                    "backup_server": asdict(s.design.roles.backup_server),
                                    "proxies": asdict(s.design.roles.proxies),
                                    "hardened_repos": asdict(s.design.roles.hardened_repos)
                                    if s.design.roles.hardened_repos
                                    else None,
                                    "gateways": asdict(s.design.roles.gateways)
                                    if s.design.roles.gateways
                                    else None,
                                },
                                "jobs": [asdict(j) for j in s.design.jobs.jobs],
                                "sobr": asdict(s.design.sobr),
                                "repo_perf": asdict(s.design.repo_perf),
                                "network": asdict(s.design.network),
                                "cost": asdict(s.design.cost),
                                "risk": asdict(s.design.risk),
                                "notes": s.design.notes,
                            },
                        }
                        for s in multi.sites
                    ],
                }
                print(json.dumps(payload, indent=2))
            else:
                print(f"Total repo across sites: {multi.total_repo_tb:.1f} TB")
                for s in multi.sites:
                    print(
                        f"- {s.name}: {s.design.repo.total_repo_tb:.1f} TB total repo, "
                        f"{s.design.roles.proxies.proxy_count} proxies"
                    )
            return
        else:
            vin = obj
    else:
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
                throughput_mb_per_core=args.throughput_mb_per_core or CONFIG["throughput_mb_per_core"],
                vm_count=args.vm_count,
                avg_vm_size_gb=args.avg_vm_size_gb,
                wan_bandwidth_mbps=args.wan_bandwidth_mbps,
                repo_type=args.repo_type,
                hypervisor=args.hypervisor,
                has_san_access=args.has_san_access,
                on_host_proxy=args.on_host_proxy,
            )

    design = design_veeam_environment(vin)

    if args.json:
        payload = {
            "input": asdict(design.input),
            "repo": asdict(design.repo),
            "roles": {
                "backup_server": asdict(design.roles.backup_server),
                "proxies": asdict(design.roles.proxies),
                "hardened_repos": asdict(design.roles.hardened_repos)
                if design.roles.hardened_repos
                else None,
                "gateways": asdict(design.roles.gateways)
                if design.roles.gateways
                else None,
            },
            "jobs": [asdict(j) for j in design.jobs.jobs],
            "sobr": asdict(design.sobr),
            "repo_perf": asdict(design.repo_perf),
            "network": asdict(design.network),
            "cost": asdict(design.cost),
            "risk": asdict(design.risk),
            "notes": design.notes,
            "blueprint": {
                "role_plan": {
                    "backup_server": asdict(design.blueprint.role_plan.backup_server),
                    "proxies": asdict(design.blueprint.role_plan.proxies),
                    "hardened_repos": asdict(design.blueprint.role_plan.hardened_repos)
                    if design.blueprint.role_plan.hardened_repos
                    else None,
                    "gateways": asdict(design.blueprint.role_plan.gateways)
                    if design.blueprint.role_plan.gateways
                    else None,
                },
                "jobs": [asdict(j) for j in design.blueprint.jobs.jobs],
                "sobr": asdict(design.blueprint.sobr),
                "repo_perf": asdict(design.blueprint.repo_perf),
                "network": asdict(design.blueprint.network),
                "cost": asdict(design.blueprint.cost),
                "notes": design.blueprint.notes,
            },
        }
        print(json.dumps(payload, indent=2))
    else:
        print_human_summary(design)


if __name__ == "__main__":
    main()
