"""WAN accelerator and backup copy job sizing."""

from __future__ import annotations

from math import ceil

from .models import WanAccelDesign, WanAccelInput


def size_wan_accel(win: WanAccelInput) -> WanAccelDesign:
    """Size WAN accelerator service data and estimate the backup-copy transfer window."""

    notes: list[str] = []
    requested_mode = (win.mode or "auto").strip().lower()
    if requested_mode not in {"auto", "low", "high", "direct"}:
        raise ValueError("WAN accelerator mode must be auto, low, high, or direct")

    if win.backup_copy_frequency_hours <= 0:
        raise ValueError("backup_copy_frequency_hours must be greater than zero")

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
        # Veeam BP: Low bandwidth is the normal WAN-accelerator mode at 1-100 Mbps.
        # Above 100 Mbps, Direct is the default architecture choice; High bandwidth mode
        # is reserved for explicit high-latency / high-change scenarios.
        mode = "low" if win.wan_mbps <= 100.0 else "direct"

    source_tb = max(0.0, win.source_tb)
    daily_change_tb = source_tb * max(0.0, win.daily_change_pct) / 100.0
    interval_hours = win.backup_copy_frequency_hours
    interval_change_tb = daily_change_tb * (interval_hours / 24.0)

    daily_change_mb = daily_change_tb * 1024.0 * 1024.0
    processing_mbps = (daily_change_mb * 8.0) / 86400.0

    if mode == "direct":
        source_count = 0
        target_count = 0
        source_digest_gb = 0
        target_digest_gb = 0
        cache_size_gb = 0
        target_total_free_space_gb = 0
        reduction_ratio = max(1.0, win.compression_ratio)
        notes.append(
            "Direct mode selected: no WAN accelerator digest or global-cache capacity is required."
        )
    else:
        # Veeam BP publishes ~500 Mbit/s average processing per target WAN accelerator.
        # Use symmetric pairs as a conservative planning topology.
        target_count = max(1, ceil(processing_mbps / 500.0))
        source_count = target_count

        digest_pct = 0.01 if mode == "high" else 0.02
        source_tb_per_accel = source_tb / source_count
        target_tb_per_accel = source_tb / target_count

        # Veeam's examples use 2 TB -> 40 GB at 2%; use decimal TB->GB for this vendor formula.
        source_digest_gb = max(1, ceil(source_tb_per_accel * 1000.0 * digest_pct))
        target_digest_gb = max(1, ceil(target_tb_per_accel * 1000.0 * digest_pct))

        if mode == "low":
            os_recommended_gb = 10 * max(0, win.os_type_count)
            cache_size_gb = max(
                40,
                int(win.cache_size_gb_per_source),
                os_recommended_gb,
            )
            target_total_free_space_gb = (
                source_count * cache_size_gb + target_count * target_digest_gb
            )
            reduction_ratio = max(1.0, win.dedupe_ratio * win.compression_ratio)
            notes.append(
                "Low bandwidth mode uses 2% digest space on source and target. Target global "
                "cache is allocated per source WAN accelerator."
            )
            notes.append(
                f"Target global cache is {cache_size_gb} GB per source connection; Veeam "
                "recommends at least 40 GB and 10 GB per unique guest OS type."
            )
        else:
            cache_size_gb = 0
            target_total_free_space_gb = target_count * target_digest_gb
            reduction_ratio = max(1.0, win.compression_ratio)
            notes.append(
                "High bandwidth mode uses 1% digest space on source and target and does not "
                "use global cache."
            )
            notes.append(
                "High bandwidth mode is explicit because Veeam BP recommends Direct above "
                "100 Mbps for normal links, reserving High mode for specific high-latency or "
                "high-change scenarios."
            )

        if target_count > 1:
            notes.append(
                f"Average raw processing demand is {processing_mbps:.1f} Mbps, so the planning "
                f"topology uses {target_count} pair(s) against Veeam's ~500 Mbps per-target "
                "processing guideline. Validate source-side concurrency separately."
            )

    interval_change_mb = interval_change_tb * 1024.0 * 1024.0
    transferred_mb = interval_change_mb / reduction_ratio
    wan_mb_per_sec = win.wan_mbps / 8.0
    backup_copy_window_hours = transferred_mb / wan_mb_per_sec / 3600.0
    meets = backup_copy_window_hours <= interval_hours
    effective_mbps = win.wan_mbps * reduction_ratio

    notes.append(
        "Transfer-window reduction is a planning assumption based on the supplied compression "
        "and deduplication ratios; measure real workload reduction before production sizing."
    )
    if mode == "high":
        notes.append(
            "The dedupe-ratio input is not applied to High mode because global cache is disabled; "
            "target-restore-point deduplication efficiency is workload-dependent."
        )
    if not meets:
        notes.append(
            f"Estimated transfer window {backup_copy_window_hours:.1f} h exceeds the configured "
            f"{interval_hours:.1f} h copy interval."
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
