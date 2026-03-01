from typing import List
from .models import RepoPerfModel, RepoSizing, VeeamInput, JobSet


def estimate_repo_perf(vin: VeeamInput, repo: RepoSizing, jobs: JobSet) -> RepoPerfModel:
    notes: List[str] = []

    daily_change_tb = vin.total_data_tb * vin.daily_change_percent / 100
    daily_backup_mb = daily_change_tb * 1024 * 1024
    backup_window_sec = vin.backup_window_hours * 3600 or 1

    required_mb_s = daily_backup_mb / backup_window_sec

    if "synthetic" in vin.backup_type:
        # Round 3: spread synthetic full load over block_generation_days windows
        block_days = max(1, vin.block_generation_days)
        syn_mb = vin.total_data_tb * 1024 * 1024
        syn_window_sec = block_days * (vin.backup_window_hours * 3600 or 1)
        synthetic_full_mb_s = syn_mb / syn_window_sec
        notes.append(
            f"Synthetic full rebuilds spread over {block_days}-day block generation period: "
            f"requires {synthetic_full_mb_s:.1f} MB/s sustained repository I/O during that window."
        )
    else:
        synthetic_full_mb_s = 0.0

    # Round 3: ReFS/XFS block-clone note
    if vin.refs_xfs:
        notes.append(
            "ReFS/XFS with block cloning enabled: synthetic full I/O cost is significantly "
            "reduced — clone operations are near-instantaneous on compatible filesystems."
        )
    else:
        notes.append(
            "ReFS/XFS not selected: synthetic full operations require full byte-copy reads/writes. "
            "Consider XFS (Linux) or ReFS (Windows) for better synthetic full performance."
        )

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
