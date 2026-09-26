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

    is_object_target = vin.repo_type == "object" or vin.direct_to_object

    if "synthetic" in vin.backup_type and vin.refs_xfs and not is_object_target:
        synthetic_full_mb_s = 0.0
        notes.append(
            "ReFS/XFS Fast Clone selected: synthetic fulls are block-cloned rather than "
            "rewritten as complete byte copies. No fabricated full-copy MB/s requirement is emitted."
        )
    elif "synthetic" in vin.backup_type:
        synthetic_full_mb = tb_to_mb(
            projected_total_data_tb(
                total_data_tb=vin.total_data_tb,
                annual_growth_percent=vin.annual_growth_percent,
                years_to_plan_for=vin.years_to_plan_for,
            )
        )
        synthetic_full_mb_s = synthetic_full_mb / backup_window_sec
        notes.append(
            "Without Fast Clone, synthetic-full planning throughput assumes the full synthesis "
            "must fit inside the configured backup window. This is a conservative planning assumption."
        )
    else:
        synthetic_full_mb_s = 0.0

    # Round 3: immutability note
    if vin.immutability_enabled and not is_object_target and not vin.refs_xfs:
        notes.append(
            "Hardened-repository immutability requires a supported Linux/XFS repository design; "
            "review the repository filesystem before deployment."
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
