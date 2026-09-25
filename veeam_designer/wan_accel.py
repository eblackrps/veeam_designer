"""WAN accelerator and backup copy job sizing."""

from __future__ import annotations

from math import ceil

from .models import WanAccelDesign, WanAccelInput


def size_wan_accel(win: WanAccelInput) -> WanAccelDesign:
    """Size WAN accelerator service data and validate the average copy window."""

    notes: list[str] = []
    requested_mode = (win.mode or "auto").strip().lower()
    if requested_mode not in {"auto", "low", "high", "direct"}:
        raise ValueError("WAN accelerator mode must be auto, low, high, or direct")

    if win.wan_mbps <= 0:
        notes.append("WAN bandwidth not specified; copy-window feasibility cannot be calculated.")
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
            mode="direct" if requested_mode == "direct" else requested_mode,
            notes=notes,
        )

    mode = requested_mode
    if mode == "auto":
        mode = "high" if win.wan_mbps > 100.0 else "low"

    daily_change_tb = max(0.0, win.source_tb) * max(0.0, win.daily_change_pct) / 100.0
    daily_change_mb = daily_change_tb * 1024.0 * 1024.0
    copy_window_seconds = max(0.01, win.backup_copy_frequency_hours) * 3600.0
    processing_mbps = daily_change_mb * 8.0 / copy_window_seconds

    if mode == "direct":
        source_count = 0
        target_count = 0
        source_digest_gb = 0
        target_digest_gb = 0
        cache_size_gb = 0
        target_total_free_space_gb = 0
        reduction_ratio = 1.0
        notes.append(
            "Direct mode selected: WAN accelerator digest and global-cache capacity are not required."
        )
    else:
        # Veeam recommends one WAN accelerator pair. Add more pairs only when the average data
        # processing rate exceeds the published ~500 Mbit/s target-accelerator guideline.
        target_count = max(1, ceil(processing_mbps / 500.0))
        source_count = target_count

        digest_pct = 0.01 if mode == "high" else 0.02
        source_tb_per_accel = max(0.0, win.source_tb) / source_count
        target_tb_per_accel = max(0.0, win.source_tb) / target_count
        source_digest_gb = max(1, ceil(source_tb_per_accel * 1024.0 * digest_pct))
        target_digest_gb = max(1, ceil(target_tb_per_accel * 1024.0 * digest_pct))

        if mode == "low":
            os_recommended_gb = 10 * max(0, win.os_type_count)
            cache_size_gb = max(
                40,
                int(win.cache_size_gb_per_source),
                os_recommended_gb,
            )
            target_total_free_space_gb = (
                source_count * cache_size_gb
                + target_count * target_digest_gb
            )
            reduction_ratio = max(1.0, win.dedupe_ratio * win.compression_ratio)
            notes.append(
                "Low Bandwidth mode: source and target digests use 2% of provisioned VM size. "
                "Target global cache is included per source accelerator."
            )
            if win.os_type_count > 0:
                notes.append(
                    f"Global cache satisfies Veeam's 10 GB per guest-OS-type recommendation "
                    f"for {win.os_type_count} OS type(s), with a 40 GB minimum."
                )
            else:
                notes.append(
                    f"Global cache uses the configured/default {cache_size_gb} GB per source "
                    "accelerator. Provide guest OS type count for a workload-specific minimum."
                )
        else:
            cache_size_gb = 0
            target_total_free_space_gb = target_count * target_digest_gb
            # High bandwidth mode does not use global cache/global block deduplication.
            reduction_ratio = max(1.0, win.compression_ratio)
            notes.append(
                "High Bandwidth mode: source and target digests use 1% of provisioned VM size "
                "and global cache is not used."
            )

        if target_count > 1:
            notes.append(
                f"Average source processing demand is {processing_mbps:.1f} Mbps, requiring "
                f"{target_count} WAN accelerator pair(s) at the 500 Mbps per-target planning limit."
            )

    transferred_mb = daily_change_mb / reduction_ratio
    wan_mb_per_sec = win.wan_mbps / 8.0
    backup_copy_window_hours = (
        transferred_mb / wan_mb_per_sec / 3600.0 if wan_mb_per_sec > 0 else 0.0
    )
    meets = backup_copy_window_hours <= win.backup_copy_frequency_hours
    effective_mbps = win.wan_mbps * reduction_ratio

    if not meets:
        notes.append(
            f"Estimated transfer window {backup_copy_window_hours:.1f} h exceeds the configured "
            f"{win.backup_copy_frequency_hours:.1f} h copy interval. Increase bandwidth, reduce "
            "change rate, or use measured reduction data."
        )
    notes.append(
        "Copy-window reduction is a planning estimate from the supplied compression/dedupe ratios; "
        "measure real workload reduction before final production sizing."
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
        backup_copy_window_hours=round(backup_copy_window_hours, 2),
        mode=mode,
        notes=notes,
    )
