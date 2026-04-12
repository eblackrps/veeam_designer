"""WAN accelerator and backup copy job sizing."""

from __future__ import annotations

from math import ceil

from .models import WanAccelDesign, WanAccelInput


def size_wan_accel(win: WanAccelInput) -> WanAccelDesign:
    """Size WAN accelerators and validate backup copy job window."""
    notes = []

    if win.wan_mbps <= 0:
        notes.append("WAN bandwidth not specified — WAN accelerator sizing skipped.")
        return WanAccelDesign(
            source_appliance_count=0,
            target_appliance_count=0,
            cache_size_gb_per_source=0,
            source_digest_gb_per_source=0,
            target_digest_gb_per_target=0,
            target_total_free_space_gb=0,
            effective_mbps=0.0,
            meets_copy_window=False,
            backup_copy_window_hours=0.0,
            notes=notes,
        )

    effective_ratio = max(1.0, win.dedupe_ratio * win.compression_ratio)
    effective_mbps = win.wan_mbps * effective_ratio
    target_count = max(1, ceil(effective_mbps / 500.0))
    source_count = target_count

    # Current UI models WAN acceleration in low-bandwidth mode per Veeam sizing guidance.
    cache_size_gb = 100
    source_digest_gb = max(1, ceil(win.source_tb * 20))
    target_digest_gb = source_digest_gb
    target_total_free_space_gb = (source_count * cache_size_gb) + target_digest_gb

    daily_change_tb = win.source_tb * (win.daily_change_pct / 100.0)
    daily_change_mb = daily_change_tb * 1024.0 * 1024.0
    effective_mb = daily_change_mb / effective_ratio
    wan_mb_per_sec = win.wan_mbps / 8.0  # Mbps → MB/s
    if wan_mb_per_sec > 0:
        bcj_window_hours = effective_mb / wan_mb_per_sec / 3600.0
    else:
        bcj_window_hours = 999.0

    meets = bcj_window_hours <= win.backup_copy_frequency_hours

    notes.append(
        "WAN accelerator disk sizing follows Veeam low-bandwidth mode guidance: source and target "
        "digest space are sized at 2% of the protected VM footprint, and target global cache "
        "defaults to 100 GB per source WAN accelerator."
    )
    notes.append(
        f"Calculated source digest space: {source_digest_gb} GB per source accelerator; target "
        f"free space requirement: {target_total_free_space_gb} GB."
    )
    if not meets:
        notes.append(
            f"BCJ window {bcj_window_hours:.1f} h exceeds frequency {win.backup_copy_frequency_hours:.0f} h "
            f"— increase WAN bandwidth or reduce source data."
        )
    if win.wan_mbps > 100:
        notes.append(
            "The WAN link is above 100 Mbps. Veeam notes that high-bandwidth links often work "
            "well without WAN acceleration and may require multiple accelerator pairs if used."
        )
    if target_count > 1:
        notes.append(
            f"Processed data rate is ~{effective_mbps:.0f} Mbps, so the calculator recommends "
            f"{target_count} accelerator pair(s) using Veeam's 500 Mbps per target accelerator guideline."
        )
    if win.source_tb > 400:
        notes.append(
            "Large source (>400 TB) — consider seeded backup copy with initial full on media."
        )

    return WanAccelDesign(
        source_appliance_count=source_count,
        target_appliance_count=target_count,
        cache_size_gb_per_source=cache_size_gb,
        source_digest_gb_per_source=source_digest_gb,
        target_digest_gb_per_target=target_digest_gb,
        target_total_free_space_gb=target_total_free_space_gb,
        effective_mbps=round(effective_mbps, 1),
        meets_copy_window=meets,
        backup_copy_window_hours=round(bcj_window_hours, 2),
        notes=notes,
    )
