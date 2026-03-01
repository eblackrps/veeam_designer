from typing import List
from .models import RepoPerfModel, RepoSizing, VeeamInput, JobSet


def estimate_repo_perf(vin: VeeamInput, repo: RepoSizing, jobs: JobSet) -> RepoPerfModel:
    notes: List[str] = []

    daily_change_tb = vin.total_data_tb * vin.daily_change_percent / 100
    daily_backup_mb = daily_change_tb * 1024 * 1024
    backup_window_sec = vin.backup_window_hours * 3600 or 1

    required_mb_s = daily_backup_mb / backup_window_sec

    if "synthetic" in vin.backup_type:
        syn_mb = vin.total_data_tb * 1024 * 1024
        syn_window_sec = vin.backup_window_hours * 3600 or 1
        synthetic_full_mb_s = syn_mb / syn_window_sec
        notes.append(
            "Synthetic fulls enabled: ensure repository can sustain periodic full rebuild "
            "on top of daily incremental load."
        )
    else:
        synthetic_full_mb_s = 0.0

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
