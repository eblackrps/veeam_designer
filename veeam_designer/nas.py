"""NAS / unstructured workload sizing aligned to Veeam published guidance."""

from __future__ import annotations

from math import ceil

from .config import CONFIG
from .models import NasDesign, NasInput
from .workload_math import projected_total_data_tb, tb_to_mb


def _compress_ratio(compress_pct: float) -> float:
    """Convert a compression-saving percentage to a storage ratio."""

    pct = max(0.0, min(compress_pct, 90.0))
    return 1.0 / (1.0 - pct / 100.0)


def _round_up_even(value: int) -> int:
    return value if value % 2 == 0 else value + 1


def size_nas(nin: NasInput) -> NasDesign:
    """Return NAS capacity and general-purpose proxy resources."""

    compression_ratio = _compress_ratio(nin.compress_pct)
    tasks_per_core = 2
    file_proxy_throughput_mb_per_core = 100.0

    effective_tb = projected_total_data_tb(
        total_data_tb=nin.source_tb,
        annual_growth_percent=nin.growth_rate_pct,
        years_to_plan_for=nin.forecast_years,
    )
    daily_change_tb = effective_tb * max(0.0, nin.daily_change_pct) / 100.0

    full_backup_tb = effective_tb / compression_ratio
    incremental_backup_tb = (
        full_backup_tb * (max(0.0, nin.daily_change_pct) / 100.0) * max(0, nin.retention_days)
    )
    backup_size_tb = full_backup_tb + incremental_backup_tb

    notes: list[str] = []

    if nin.object_storage:
        metadata_tb = backup_size_tb * 0.05
        primary_repo_tb = backup_size_tb + metadata_tb

        # Current Veeam cache-repository guidance: >=1 GB active metadata per 1M file
        # versions protected by one job. We only know current file count, so expose a
        # one-version-per-file, one-job minimum rather than inventing a source-capacity ratio.
        active_metadata_gb = max(1, ceil(max(0.0, nin.file_count_millions)))
        cache_repo_tb = active_metadata_gb / 1024.0
        notes.append(
            f"Object-target cache minimum uses {active_metadata_gb} GB for the supplied "
            f"{nin.file_count_millions:.1f} million files, assuming one active version per file "
            "and one protecting job. Additional versions or jobs increase cache requirements."
        )
    else:
        metadata_tb = backup_size_tb * 0.10
        workspace_tb = backup_size_tb * 0.10
        primary_repo_tb = backup_size_tb + metadata_tb + workspace_tb
        cache_repo_tb = 0.0
        notes.append(
            "Disk-backed NAS repository includes Veeam's 10% metadata and 10% workspace "
            "planning allowances."
        )

    total_repo_tb = primary_repo_tb + cache_repo_tb

    if nin.backup_window_hours > 0:
        required_mb_s = tb_to_mb(daily_change_tb) / (nin.backup_window_hours * 3600.0)
        files_per_hour = (nin.file_count_millions * 1_000_000.0) / nin.backup_window_hours
    else:
        required_mb_s = 0.0
        files_per_hour = 0.0

    throughput_processing_cores = (
        ceil((required_mb_s / file_proxy_throughput_mb_per_core) / tasks_per_core)
        if required_mb_s
        else 0
    )
    file_processing_cores = (
        ceil((files_per_hour / 5_000_000.0) / tasks_per_core) if files_per_hour else 0
    )
    processing_cores = _round_up_even(max(2, throughput_processing_cores, file_processing_cores))

    # Two proxies provide production availability when the workload has multiple shares.
    proxy_count = 2 if nin.share_count > 1 else 1
    os_cores = 2 * proxy_count
    os_ram_gb = 4 * proxy_count
    processing_ram_gb = ceil(processing_cores * 1.33 * tasks_per_core)
    file_proxy_cores = processing_cores + os_cores
    file_proxy_ram_gb = processing_ram_gb + os_ram_gb

    notes.append(
        f"General-purpose proxy processing uses Veeam BP values of 100 MB/s per core or "
        f"5 million files/hour per task, at {tasks_per_core} tasks/core. The higher requirement "
        f"is rounded to an even {processing_cores} processing cores."
    )
    notes.append(
        f"Provisioned total for {proxy_count} proxy/proxies adds 2 OS cores and 4 GB OS RAM per "
        f"proxy: {file_proxy_cores} vCPU / {file_proxy_ram_gb} GB RAM total."
    )

    if nin.storage_native_cft:
        notes.append(
            "Storage-native CFT enabled: scanning behavior can improve on supported filers, but "
            "proxy throughput and source/storage limits still require validation."
        )
    if nin.immutability_enabled:
        notes.append("Immutability requires a supported immutable target; no arbitrary capacity tax is added.")
    if nin.gfs_weekly or nin.gfs_monthly or nin.gfs_yearly:
        notes.append(
            "NAS backup uses an incremental-forever chain. Weekly/monthly/yearly GFS counts are "
            "not separately added in this calculator mode."
        )
    if total_repo_tb > float(CONFIG["warn_repo_tb"]):
        notes.append(
            f"NAS repository footprint ({total_repo_tb:.1f} TB) exceeds the configured review threshold."
        )

    return NasDesign(
        cache_repo_tb=round(cache_repo_tb, 3),
        primary_repo_tb=round(primary_repo_tb, 1),
        gfs_repo_tb=0.0,
        total_repo_tb=round(total_repo_tb, 1),
        file_proxy_cores=file_proxy_cores,
        file_proxy_ram_gb=file_proxy_ram_gb,
        file_proxy_count=proxy_count,
        notes=notes,
    )
