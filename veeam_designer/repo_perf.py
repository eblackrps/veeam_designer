from typing import List

from .models import JobSet, RepoPerfModel, RepoSizing, VeeamInput
from .workload_math import projected_daily_change_tb, projected_total_data_tb, tb_to_mb


def estimate_repo_perf(vin: VeeamInput, repo: RepoSizing, jobs: JobSet) -> RepoPerfModel:
    notes: List[str] = []

    daily_change_size_tb = projected_daily_change_tb(
        total_data_tb=vin.total_data_tb,
        daily_change_percent=vin.daily_change_percent,
        annual_growth_percent=vin.annual_growth_percent,
        years_to_plan_for=vin.years_to_plan_for,
    )
    daily_backup_mb = tb_to_mb(daily_change_size_tb)
    backup_window_sec = vin.backup_window_hours * 3600 or 1

    required_mb_s = daily_backup_mb / backup_window_sec

    if "synthetic" in vin.backup_type and not vin.refs_xfs:
        block_days = max(1, vin.block_generation_days)
        syn_mb = tb_to_mb(
            projected_total_data_tb(
                total_data_tb=vin.total_data_tb,
                annual_growth_percent=vin.annual_growth_percent,
                years_to_plan_for=vin.years_to_plan_for,
            )
        )
        syn_window_sec = block_days * (vin.backup_window_hours * 3600 or 1)
        synthetic_full_mb_s = syn_mb / syn_window_sec
        notes.append(
            f"Synthetic full byte-copy path without Fast Clone: {synthetic_full_mb_s:.1f} MB/s "
            f"sustained repository I/O when spread across {block_days} backup window(s)."
        )
    elif "synthetic" in vin.backup_type:
        synthetic_full_mb_s = 0.0
        notes.append(
            "ReFS/XFS Fast Clone selected: a synthetic full is block-cloned rather than rewritten "
            "as a complete byte-copy, so no fake full-copy MB/s requirement is emitted."
        )
    else:
        synthetic_full_mb_s = 0.0


    # Round 3: immutability note
    if vin.immutability_enabled and not vin.refs_xfs:
        notes.append(
            "Immutability requested but ReFS/XFS is not enabled. "
            "Object-lock immutability on Linux hardened repos requires XFS; "
            "enable refs_xfs or choose an object storage target."
        )

    if repo.total_repo_tb > 300:
        notes.append(
            "Large repository footprint: prefer multiple extents / SOBR and fast filesystems "
            "such as XFS/ReFS with block cloning."
        )

    return RepoPerfModel(
        required_mb_s=round(required_mb_s, 1),
        synthetic_full_mb_s=round(synthetic_full_mb_s, 1),
        notes=notes,
    )
