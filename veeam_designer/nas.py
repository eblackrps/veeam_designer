"""NAS / unstructured workload sizing aligned to Veeam NAS best-practice formulas."""

from __future__ import annotations

from math import ceil

from .config import CONFIG
from .models import NasDesign, NasInput
from .workload_math import projected_total_data_tb, tb_to_mb


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
    file_proxy_throughput_mb_per_core = 100.0

    effective_tb = projected_total_data_tb(
        total_data_tb=nin.source_tb,
        annual_growth_percent=nin.growth_rate_pct,
        years_to_plan_for=nin.forecast_years,
    )
    daily_change_tb = effective_tb * nin.daily_change_pct / 100.0

    full_backup_tb = effective_tb / compression_ratio
    incremental_backup_tb = full_backup_tb * (nin.daily_change_pct / 100.0) * nin.retention_days
    backup_size_tb = full_backup_tb + incremental_backup_tb

    if nin.object_storage:
        metadata_tb = backup_size_tb * 0.05
        primary_repo_tb = backup_size_tb + metadata_tb
        cache_repo_tb = max(0.01, effective_tb * 0.05)
    else:
        metadata_tb = backup_size_tb * 0.10
        workspace_tb = backup_size_tb * 0.10
        primary_repo_tb = backup_size_tb + metadata_tb + workspace_tb
        cache_repo_tb = 0.0

    total_repo_tb = primary_repo_tb + cache_repo_tb
    if nin.backup_window_hours > 0:
        required_mb_s = tb_to_mb(daily_change_tb) / (nin.backup_window_hours * 3600.0)
        files_per_hour = (nin.file_count_millions * 1_000_000.0) / nin.backup_window_hours
    else:
        required_mb_s = 0.0
        files_per_hour = 0.0

    throughput_cores = (
        ceil(required_mb_s / file_proxy_throughput_mb_per_core) if required_mb_s else 0
    )
    file_inventory_cores = ceil(files_per_hour / 5_000_000.0) if files_per_hour else 0
    file_proxy_cores = max(2, throughput_cores, file_inventory_cores)
    file_proxy_ram_gb = max(8, ceil(file_proxy_cores * 1.33))

    notes: list[str] = []
    if nin.storage_native_cft:
        notes.append(
            "Storage-native CFT enabled: Veeam will use the filer's own change-tracking API "
            "instead of scanning. Requires compatible NAS vendor support."
        )
    if nin.immutability_enabled:
        notes.append(
            "Immutability enabled: object-lock or hardened repo required for the backup target."
        )
    if nin.gfs_weekly or nin.gfs_monthly or nin.gfs_yearly:
        notes.append(
            "Veeam NAS backup uses an incremental-forever chain. Weekly, monthly, and yearly GFS "
            "counts are ignored in this calculator mode."
        )
    if nin.object_storage:
        notes.append(
            "Cache repository disk sizing follows Veeam's recommendation to reserve at least 5% "
            "of source capacity for NAS metadata when backing up directly to object storage."
        )
    else:
        notes.append(
            "For disk-backed NAS repositories, Veeam notes that cache-repository disk usage is "
            "usually small enough that dedicated disk sizing is not required."
        )
    notes.append(
        "File proxy throughput follows Veeam published initial sizing figures and should be split "
        "across at least two proxies for production availability."
    )
    if total_repo_tb > float(CONFIG["warn_repo_tb"]):
        notes.append(
            f"NAS repo footprint ({total_repo_tb:.1f} TB) exceeds threshold. "
            "Consider SOBR with capacity tier."
        )

    return NasDesign(
        cache_repo_tb=round(cache_repo_tb, 2),
        primary_repo_tb=round(primary_repo_tb, 1),
        gfs_repo_tb=0.0,
        total_repo_tb=round(total_repo_tb, 1),
        file_proxy_cores=file_proxy_cores,
        file_proxy_ram_gb=file_proxy_ram_gb,
        notes=notes,
    )
