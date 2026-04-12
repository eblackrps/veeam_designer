"""
NAS / Unstructured workload sizing module.

Mirrors the Veeam Calculator – Unstructured / NAS tab behaviour:
  - Cache repository for file change-tracking metadata
  - Primary repository sized from daily change rate and retention
  - File proxy cores and RAM (lighter than VM proxy: 10 MB/s per core)
  - GFS copies sized the same way as the VM engine
  - Compress-by percentage (Media 10 % / Mix 30 % / Docs 50 %) converts to ratio
"""

from __future__ import annotations

from math import ceil

from .config import CONFIG
from .models import NasDesign, NasInput


def _compress_ratio(compress_pct: float) -> float:
    """Convert a compression-saving percentage to a storage ratio.

    compress_pct=30 means 30 % smaller → store 70 % → ratio = 1/0.70 ≈ 1.43
    Clamped so we never divide by zero or produce ratios below 1.
    """
    pct = max(0.0, min(compress_pct, 90.0))
    return 1.0 / (1.0 - pct / 100.0)


def size_nas(nin: NasInput) -> NasDesign:
    """Return a NasDesign for the given NasInput."""
    compression_ratio = _compress_ratio(nin.compress_pct)

    # Effective source after growth forecast
    effective_tb = nin.source_tb * (1.0 + nin.growth_rate_pct / 100.0 * nin.forecast_years)
    daily_change_tb = effective_tb * nin.daily_change_pct / 100.0

    # Primary repo: full dataset + incremental run-of-day × retention
    # Overhead factor matches VM engine (1.25) then GFS overhead (1.1)
    primary_logical_tb = effective_tb + daily_change_tb * nin.retention_days
    primary_repo_tb = (primary_logical_tb / compression_ratio) * CONFIG["repo_overhead_factor"]

    # GFS copies (one full per period, compressed)
    gfs_tb = (
        nin.gfs_weekly * effective_tb / compression_ratio
        + nin.gfs_monthly * effective_tb / compression_ratio
        + nin.gfs_yearly * effective_tb / compression_ratio
    ) * CONFIG["gfs_overhead_factor"]

    # Cache repository: Veeam stores per-share block-change metadata
    # Rule of thumb: ~1 GB per million files per share
    cache_repo_tb = (nin.file_count_millions * 0.001) * nin.share_count
    cache_repo_tb = max(0.01, cache_repo_tb)  # always at least 10 GB

    total_repo_tb = primary_repo_tb + gfs_tb + cache_repo_tb

    # File proxy sizing (NAS: 10 MB/s per core, vs 15 MB/s for VM HotAdd)
    if nin.backup_window_hours > 0:
        required_mb_s = (daily_change_tb * 1024.0 * 1024.0) / (nin.backup_window_hours * 3600.0)
    else:
        required_mb_s = 0.0

    file_proxy_cores = max(2, ceil(required_mb_s / 10.0))
    file_proxy_ram_gb = max(4, file_proxy_cores * 2)

    notes: list = []
    if nin.storage_native_cft:
        notes.append(
            "Storage-native CFT enabled: Veeam will use the filer's own change-tracking API "
            "instead of scanning. Requires compatible NAS vendor support."
        )
    if nin.immutability_enabled:
        notes.append(
            "Immutability enabled: object-lock or hardened repo required for the backup target."
        )
    if total_repo_tb > CONFIG["warn_repo_tb"]:
        notes.append(
            f"NAS repo footprint ({total_repo_tb:.1f} TB) exceeds threshold. "
            "Consider SOBR with capacity tier."
        )

    return NasDesign(
        cache_repo_tb=round(cache_repo_tb, 2),
        primary_repo_tb=round(primary_repo_tb, 1),
        gfs_repo_tb=round(gfs_tb, 1),
        total_repo_tb=round(total_repo_tb, 1),
        file_proxy_cores=file_proxy_cores,
        file_proxy_ram_gb=file_proxy_ram_gb,
        notes=notes,
    )
