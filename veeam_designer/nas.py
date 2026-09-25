"""NAS / unstructured workload sizing aligned to Veeam published guidance."""

from __future__ import annotations

from math import ceil

from .config import CONFIG
from .models import NasDesign, NasInput
from .workload_math import projected_total_data_tb


def _compress_ratio(compress_pct: float) -> float:
    """Convert a compression-saving percentage to a storage ratio."""

    pct = max(0.0, min(compress_pct, 90.0))
    return 1.0 / (1.0 - pct / 100.0)


def size_nas(nin: NasInput) -> NasDesign:
    """Return NAS capacity and general-purpose proxy resources."""

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

    concurrent_sources = max(1, min(max(1, nin.share_count), nin.concurrent_sources))
    proxy_count = 2 if nin.share_count > 1 else 1
    sources_per_proxy = max(1, ceil(concurrent_sources / proxy_count))

    if nin.object_storage:
        file_proxy_cores_each = 2 + (6 * sources_per_proxy)
        file_proxy_ram_gb_each = 4 + (16 * sources_per_proxy)
        target_basis = "object-storage target"
    else:
        file_proxy_cores_each = 2 + (4 * sources_per_proxy)
        file_proxy_ram_gb_each = 4 + (4 * sources_per_proxy)
        target_basis = "direct/NAS/deduplicating target"

    file_proxy_cores = proxy_count * file_proxy_cores_each
    file_proxy_ram_gb = proxy_count * file_proxy_ram_gb_each

    notes.append(
        f"General-purpose proxy sizing follows Veeam 13.1 unstructured-data requirements for a "
        f"{target_basis}: {file_proxy_cores_each} vCPU / {file_proxy_ram_gb_each} GB RAM per "
        f"proxy at {sources_per_proxy} concurrently processed source(s) per proxy."
    )
    if proxy_count > 1:
        notes.append(
            "Two proxies are included for production availability, matching Veeam's recommendation "
            "to select at least two proxies for file-share backup."
        )
    notes.append(
        f"Concurrent source count is explicit ({concurrent_sources}). File count and backup window "
        "are not converted into CPU with an unpublished throughput heuristic."
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
        file_proxy_cores_each=file_proxy_cores_each,
        file_proxy_ram_gb_each=file_proxy_ram_gb_each,
        notes=notes,
    )
