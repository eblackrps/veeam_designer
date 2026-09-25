"""NAS / unstructured workload sizing aligned to current Veeam guidance."""

from __future__ import annotations

from math import ceil

from .config import CONFIG
from .models import NasDesign, NasInput
from .workload_math import projected_total_data_tb


def _compress_ratio(compress_pct: float) -> float:
    """Convert an explicit data-reduction percentage to a storage ratio."""

    pct = max(0.0, min(compress_pct, 90.0))
    return 1.0 / (1.0 - pct / 100.0)


def _round_up_even(value: int) -> int:
    return value if value % 2 == 0 else value + 1


def size_nas(nin: NasInput) -> NasDesign:
    """Return NAS capacity, general-purpose proxy, and cache-repository resources."""

    if nin.backup_window_hours <= 0:
        raise ValueError("backup_window_hours must be greater than zero")

    compression_ratio = _compress_ratio(nin.compress_pct)
    effective_tb = projected_total_data_tb(
        total_data_tb=nin.source_tb,
        annual_growth_percent=nin.growth_rate_pct,
        years_to_plan_for=nin.forecast_years,
    )

    full_backup_tb = effective_tb / compression_ratio
    incremental_backup_tb = (
        full_backup_tb
        * (max(0.0, nin.daily_change_pct) / 100.0)
        * max(0, int(nin.retention_days))
    )
    backup_size_tb = full_backup_tb + incremental_backup_tb

    notes: list[str] = [
        f"Data reduction is an explicit input: {max(0.0, min(nin.compress_pct, 90.0)):.1f}%."
    ]

    if nin.object_storage:
        metadata_tb = backup_size_tb * 0.05
        primary_repo_tb = backup_size_tb + metadata_tb

        # Veeam User Guide: >=1 GB active metadata per 1M file versions per protecting job.
        active_metadata_gb = max(1, ceil(max(0.0, nin.file_count_millions)))
        cache_repo_tb = active_metadata_gb / 1024.0
        notes.append(
            "Object-target capacity uses Veeam Best Practice's 5% metadata formula and no "
            "workspace reserve."
        )
        notes.append(
            f"Object-target cache repository reserves {active_metadata_gb} GB for the supplied "
            f"{nin.file_count_millions:.1f} million file versions, assuming one active version "
            "per file and one protecting job. More versions or jobs increase the requirement."
        )
    else:
        # The current Veeam BP page is internally inconsistent: its formula table states
        # 10% metadata + 10% workspace while worked examples show 5% + 5%.
        # Use the conservative published table values and call the ambiguity out explicitly.
        metadata_tb = backup_size_tb * 0.10
        workspace_tb = backup_size_tb * 0.10
        primary_repo_tb = backup_size_tb + metadata_tb + workspace_tb
        cache_repo_tb = 0.0
        notes.append(
            "Disk-target capacity uses the conservative Veeam Best Practice formula-table "
            "values: 10% metadata plus 10% workspace. The same BP page's worked examples show "
            "5% + 5%, so this is a documented-source ambiguity rather than hidden precision."
        )

    total_repo_tb = primary_repo_tb + cache_repo_tb

    # Veeam BP proxy model:
    # 100 MB/s ~= 0.34 TB/h/core; 5M files/h/task; 2 tasks/core; 1.33 GB RAM/core/task.
    tasks_per_core = 2
    incremental_tb_per_hour = (
        effective_tb * (max(0.0, nin.daily_change_pct) / 100.0) / nin.backup_window_hours
    )
    files_m_per_hour = max(0.0, nin.file_count_millions) / nin.backup_window_hours

    throughput_cores = ceil((incremental_tb_per_hour / 0.34) / tasks_per_core)
    file_processing_cores = ceil((files_m_per_hour / 5.0) / tasks_per_core)
    processing_cores = _round_up_even(max(2, throughput_cores, file_processing_cores))
    processing_ram_gb = ceil(processing_cores * 1.33 * tasks_per_core)

    proxy_count = 2 if nin.share_count > 1 else 1
    concurrent_sources = max(1, min(max(1, nin.share_count), max(1, nin.concurrent_sources)))
    tasks_per_proxy = max(1, ceil(concurrent_sources / proxy_count))

    bp_cores_each = ceil((processing_cores + (2 * proxy_count)) / proxy_count)
    bp_ram_each = ceil((processing_ram_gb + (4 * proxy_count)) / proxy_count)

    system_min_cores_each = max(4, 2 * tasks_per_proxy)
    system_min_ram_each = 4 + (4 * tasks_per_proxy)

    file_proxy_cores_each = max(bp_cores_each, system_min_cores_each)
    file_proxy_ram_gb_each = max(bp_ram_each, system_min_ram_each)
    file_proxy_cores = proxy_count * file_proxy_cores_each
    file_proxy_ram_gb = proxy_count * file_proxy_ram_gb_each

    notes.append(
        f"General-purpose proxy BP model calculates {processing_cores} processing core(s) and "
        f"{processing_ram_gb} GB processing RAM before OS/system minimums. Final plan: "
        f"{proxy_count} proxy/proxies at {file_proxy_cores_each} vCPU / "
        f"{file_proxy_ram_gb_each} GB RAM each."
    )
    if proxy_count > 1:
        notes.append(
            "Two proxies are included for multi-share availability, matching Veeam's recommendation "
            "to select at least two proxies."
        )

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
            "Storage-native CFT can reduce source scanning on supported filers; it does not "
            "change published proxy/cache minimums."
        )
    if nin.immutability_enabled:
        notes.append(
            "Immutability requires a supported immutable target; no arbitrary capacity percentage "
            "is added."
        )
    if nin.gfs_weekly or nin.gfs_monthly or nin.gfs_yearly:
        notes.append(
            "NAS backup uses an incremental-forever short-term chain. GFS counts are not "
            "separately converted into fabricated full-backup capacity in this model."
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
