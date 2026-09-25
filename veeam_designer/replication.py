"""VM replication and CDP sizing."""

from __future__ import annotations

from math import ceil

from .models import ReplicationDesign, ReplicationInput


def _cdp_proxy_resources(required_mb_s: float) -> tuple[int, int, int]:
    """Return count per side, vCPU per proxy, and RAM GB per proxy."""

    proxy_count = max(1, ceil(required_mb_s / 960.0))
    per_proxy_mb_s = required_mb_s / proxy_count if proxy_count else 0.0

    if per_proxy_mb_s <= 480.0:
        cores, ram_gb = 4, 8
    elif per_proxy_mb_s <= 720.0:
        cores, ram_gb = 6, 12
    else:
        cores, ram_gb = 8, 16

    return proxy_count, cores, ram_gb


def size_replication(rin: ReplicationInput) -> ReplicationDesign:
    """Size steady-state replication bandwidth and optional CDP infrastructure."""

    daily_change_tb = rin.source_tb * max(0.0, rin.daily_change_pct) / 100.0
    daily_change_mb = daily_change_tb * 1024.0 * 1024.0

    # With a uniform change rate, the sustained transfer rate needed to keep pace is the
    # daily changed data divided by one day. RPO affects latency tolerance, not this average.
    required_mb_s = daily_change_mb / 86400.0
    required_mbps = required_mb_s * 8.0
    meets_rpo = rin.wan_mbps > 0 and required_mbps <= rin.wan_mbps

    # Replication creates a target VM copy. Transport compression changes bytes on the wire,
    # not the provisioned target VM footprint.
    replica_storage_tb = max(0.0, rin.source_tb)

    cdp_proxy_count = 0
    cdp_proxy_cores = 0
    cdp_proxy_ram_gb = 0
    cdp_proxy_cache_gb = 0
    cdp_journal_tb = 0.0
    notes: list[str] = [
        "Replication bandwidth is a steady-state average based on the configured daily change "
        "rate. It does not guarantee the requested RPO during bursts, backlog, or latency events.",
        "Replica storage is reported as the source VM footprint. Additional replica restore-point "
        "delta/checkpoint space is not estimated because replica retention is not an input.",
    ]

    if rin.cdp_enabled:
        retention_hours = max(0.0, rin.cdp_retention_hours)
        cdp_journal_tb = daily_change_tb * (retention_hours / 24.0)
        cdp_proxy_count, cdp_proxy_cores, cdp_proxy_ram_gb = _cdp_proxy_resources(required_mb_s)
        cdp_proxy_cache_gb = 50

        notes.append(
            f"CDP short-term journal uses the configured {retention_hours:g}-hour retention "
            f"window: {cdp_journal_tb:.2f} TB at the stated average change rate."
        )
        notes.append(
            f"CDP requires {cdp_proxy_count} source and {cdp_proxy_count} target proxy/proxies; "
            f"each is sized at {cdp_proxy_cores} vCPU / {cdp_proxy_ram_gb} GB RAM from Veeam's "
            "published virtual CDP proxy throughput tiers."
        )
        notes.append(
            "Each CDP proxy requires at least 50 GB of disk-based write-I/O cache. "
            "Actual cache demand can be higher during connectivity interruptions."
        )

    if rin.wan_mbps <= 0:
        notes.append("No WAN bandwidth specified; steady-state transfer feasibility was not validated.")
    elif not meets_rpo:
        notes.append(
            f"Average changed-data rate requires {required_mbps:.1f} Mbps, above the configured "
            f"{rin.wan_mbps:.1f} Mbps. Backlog will grow even before burst/latency effects."
        )
    else:
        notes.append(
            f"Configured WAN bandwidth exceeds the {required_mbps:.1f} Mbps average changed-data "
            "rate. Validate burst behavior and latency against the requested RPO."
        )

    return ReplicationDesign(
        required_mbps=round(required_mbps, 1),
        meets_rpo=meets_rpo,
        replica_storage_tb=round(replica_storage_tb, 1),
        cdp_proxy_count_per_side=cdp_proxy_count,
        cdp_proxy_cores=cdp_proxy_cores,
        cdp_proxy_ram_gb=cdp_proxy_ram_gb,
        cdp_proxy_cache_gb=cdp_proxy_cache_gb,
        cdp_journal_tb=round(cdp_journal_tb, 2),
        notes=notes,
    )
