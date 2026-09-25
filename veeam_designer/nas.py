"""NAS / unstructured workload sizing aligned to current Veeam guidance."""

from __future__ import annotations

from math import ceil

from .config import CONFIG
from .models import NasDesign, NasInput
from .workload_math import projected_total_data_tb


def _compress_ratio(compress_pct: float) -> float:
    """Convert a compression-saving percentage to a storage ratio."""

    pct = max(0.0, min(compress_pct, 90.0))
    return 1.0 / (1.0 - pct / 100.0)


def _round_up_even(value: int) -> int:
    return value if value % 2 == 0 else value + 1


def size_nas(nin: NasInput) -> NasDesign:
    """Return NAS capacity, general-purpose proxy, and cache-repository resources."""

    compression_ratio = _compress_ratio(nin.compress_pct)
    effective_tb = projected_total_data_tb(
        total_data_tb=nin.source_tb,
        annual_growth_percent=nin.growth_rate_pct,
        years_to_plan_for=nin.forecast_years,
    )

    full_backup_tb = effective_tb / compression_ratio
    incremental_backup_tb = (
        full_backup_tb * (max(0.0, nin.daily_change_pct) / 100.0) * max(0, nin.retention_days)
    )
    backup_size_tb = full_backup_tb + incremental_backup_tb

    notes: list[str] = []

    if nin.object_storage:
        metadata_tb = backup_size_tb * 0.05
        primary_repo_tb = backup_size_tb + metadata_tb

        # Current Veeam cache guidance: >=1 GB active metadata per 1M file versions per job.
        active_metadata_gb = max(1, ceil(max(0.0, nin.file_count_millions)))
        cache_repo_tb = active_metadata_gb / 1024.0
        notes.append(
            f"Object-target cache minimum uses {active_metadata_gb} GB for the supplied "
            f"{nin.file_count_millions:.1f} million files, assuming one active version per file "
            "and one protecting job. Additional versions or jobs increase cache requirements."
        )
    else:
        metadata_tb = backup_size_tb * 0.05
        workspace_tb = backup_size_tb * 0.05
        primary_repo_tb = backup_size_tb + metadata_tb + workspace_tb
        cache_repo_tb = 0.0
        notes.append(
            "Disk-backed NAS repository includes Veeam Best Practice allowances of 5% metadata "
            "and 5% workspace."
        )

    total_repo_tb = primary_repo_tb + cache_repo_tb

    # Veeam BP proxy sizing:
    # - 100 MB/s ~= 0.34 TB/h per proxy CPU core
    # - 5 million files/hour per proxy task
    # - 2 tasks/core (current VBR planning target)
    # - 1.33 GB RAM/core/task, plus 2 cores / 4 GB for the OS per proxy.
    tasks_per_core = 2
    backup_window_hours = max(0.01, nin.backup_window_hours)
    incremental_tb_per_hour = (
        effective_tb * (max(0.0, nin.daily_change_pct) / 100.0) / backup_window_hours
    )
    files_m_per_hour = max(0.0, nin.file_count_millions) / backup_window_hours

    throughput_cores = ceil((incremental_tb_per_hour / 0.34) / tasks_per_core)
    file_processing_cores = ceil((files_m_per_hour / 5.0) / tasks_per_core)
    processing_cores = _round_up_even(max(2, throughput_cores, file_processing_cores))
    processing_ram_gb = ceil(processing_cores * 1.33 * tasks_per_core)

    proxy_count = 2 if nin.share_count > 1 else 1
    concurrent_sources = max(1, min(max(1, nin.share_count), nin.concurrent_sources))
    tasks_per_proxy = max(1, ceil(concurrent_sources / proxy_count))

    bp_cores_each = ceil((processing_cores + (2 * proxy_count)) / proxy_count)
    bp_ram_each = ceil((processing_ram_gb + (4 * proxy_count)) / proxy_count)

    # Current user-guide minimums for unstructured-data proxy tasks.
    system_min_cores_each = max(4, 2 * tasks_per_proxy)
    system_min_ram_each = 4 + (4 * tasks_per_proxy)

    file_proxy_cores_each = max(bp_cores_each, system_min_cores_each)
    file_proxy_ram_gb_each = max(bp_ram_each, system_min_ram_each)
    file_proxy_cores = proxy_count * file_proxy_cores_each
    file_proxy_ram_gb = proxy_count * file_proxy_ram_gb_each

    notes.append(
        f"General-purpose proxy processing requires {processing_cores} processing core(s) and "
        f"{processing_ram_gb} GB processing RAM from the Veeam BP throughput/file-count model; "
        f"OS and current system minimums produce {proxy_count} proxy/proxies at "
        f"{file_proxy_cores_each} vCPU / {file_proxy_ram_gb_each} GB RAM each."
    )
    if proxy_count > 1:
        notes.append(
            "Two proxies are included for file-share availability, matching Veeam's recommendation "
            "to select at least two proxies."
        )

    # Cache-repository compute is target dependent in the current Veeam User Guide.
    if nin.object_storage:
        cache_repo_cores = 2 + (6 * concurrent_sources)
        cache_repo_ram_gb = 4 + (16 * concurrent_sources)
        cache_basis = "object-storage target"
    else:
        cache_repo_cores = 2 + (4 * concurrent_sources)
        cache_repo_ram_gb = 4 + (4 * concurrent_sources)
        cache_basis = "direct/NAS/deduplicating target"
    notes.append(
        f"Cache-repository compute for {concurrent_sources} concurrent source(s) and a "
        f"{cache_basis}: {cache_repo_cores} vCPU / {cache_repo_ram_gb} GB RAM."
    )

    if nin.storage_native_cft:
        notes.append(
            "Storage-native CFT can reduce source scanning on supported filers; it does not change "
            "the published proxy or cache-repository minimums."
        )
    if nin.immutability_enabled:
        notes.append(
            "Immutability requires a supported immutable target; no arbitrary capacity percentage "
            "is added."
        )
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
        file_proxy_cores_each=file_proxy_cores_each,
        file_proxy_ram_gb_each=file_proxy_ram_gb_each,
        cache_repo_cores=cache_repo_cores,
        cache_repo_ram_gb=cache_repo_ram_gb,
        notes=notes,
    )
