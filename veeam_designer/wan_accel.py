"""WAN accelerator and backup copy job sizing."""
from __future__ import annotations
from math import ceil
from veeam_designer.models import WanAccelInput, WanAccelDesign


def size_wan_accel(win: WanAccelInput) -> WanAccelDesign:
    """Size WAN accelerators and validate backup copy job window."""
    notes = []

    if win.wan_mbps <= 0:
        notes.append("WAN bandwidth not specified — WAN accelerator sizing skipped.")
        return WanAccelDesign(
            source_appliance_count=0,
            target_appliance_count=0,
            cache_size_gb_per_source=0,
            effective_mbps=0.0,
            meets_copy_window=False,
            backup_copy_window_hours=0.0,
            notes=notes,
        )

    cache_size_gb = max(10, ceil(win.source_tb * 10))
    effective_ratio = win.dedupe_ratio * win.compression_ratio
    effective_mbps = win.wan_mbps * effective_ratio

    # Daily change estimate (5% of source)
    daily_change_tb = win.source_tb * 0.05
    # Bytes to transfer per BCJ cycle
    bytes_to_xfer = daily_change_tb * 1024 ** 3 / effective_ratio
    wan_bytes_per_sec = (win.wan_mbps / 8.0) * 1_000_000
    if wan_bytes_per_sec > 0:
        bcj_window_hours = bytes_to_xfer / wan_bytes_per_sec / 3600.0
    else:
        bcj_window_hours = 999.0

    meets = bcj_window_hours <= win.backup_copy_frequency_hours
    source_count = max(1, ceil(win.source_tb / 200.0))
    target_count = source_count

    if effective_mbps < win.wan_mbps:
        notes.append(
            f"Raw WAN: {win.wan_mbps:.0f} Mbps — effective with dedupe/compress: {effective_mbps:.0f} Mbps."
        )
    if not meets:
        notes.append(
            f"BCJ window {bcj_window_hours:.1f} h exceeds frequency {win.backup_copy_frequency_hours:.0f} h "
            f"— increase WAN bandwidth or reduce source data."
        )
    if win.source_tb > 400:
        notes.append("Large source (>400 TB) — consider seeded backup copy with initial full on media.")

    return WanAccelDesign(
        source_appliance_count=source_count,
        target_appliance_count=target_count,
        cache_size_gb_per_source=cache_size_gb,
        effective_mbps=round(effective_mbps, 1),
        meets_copy_window=meets,
        backup_copy_window_hours=round(bcj_window_hours, 2),
        notes=notes,
    )
