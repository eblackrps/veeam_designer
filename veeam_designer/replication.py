"""VM replication and CDP sizing."""

from __future__ import annotations

from math import ceil

from .models import ReplicationDesign, ReplicationInput


def _cdp_proxy_resources(
    processing_mb_s: float,
    network_encryption: bool,
) -> tuple[int, int, int]:
    """Return proxy count per side, vCPU per proxy, and RAM GB per proxy."""

    max_per_proxy = 720.0 if network_encryption else 960.0
    proxy_count = max(1, ceil(max(0.0, processing_mb_s) / max_per_proxy))
    per_proxy_mb_s = processing_mb_s / proxy_count if proxy_count else 0.0

    if network_encryption:
        if per_proxy_mb_s <= 360.0:
            cores, ram_gb = 4, 8
        elif per_proxy_mb_s <= 540.0:
            cores, ram_gb = 6, 12
        else:
            cores, ram_gb = 8, 16
    else:
        if per_proxy_mb_s <= 480.0:
            cores, ram_gb = 4, 8
        elif per_proxy_mb_s <= 720.0:
            cores, ram_gb = 6, 12
        else:
            cores, ram_gb = 8, 16

    return proxy_count, cores, ram_gb


def size_replication(rin: ReplicationInput) -> ReplicationDesign:
    """Size steady-state replication bandwidth and optional CDP infrastructure."""

    source_tb = max(0.0, rin.source_tb)
    daily_change_tb = source_tb * max(0.0, rin.daily_change_pct) / 100.0
    daily_change_mb = daily_change_tb * 1024.0 * 1024.0

    # Average bandwidth required to prevent backlog. RPO changes the restore-point cadence,
    # not the average number of changed bytes produced per day.
    required_mb_s = daily_change_mb / 86400.0
    required_mbps = required_mb_s * 8.0
    meets_rpo = rin.wan_mbps > 0 and required_mbps <= rin.wan_mbps

    # Transport compression affects bytes on the wire, not provisioned replica VM capacity.
    replica_storage_tb = source_tb

    cdp_proxy_count = 0
    cdp_proxy_cores = 0
    cdp_proxy_ram_gb = 0
    cdp_proxy_cache_gb = 0
    cdp_journal_tb = 0.0

    notes: list[str] = [
        "Replication bandwidth is a steady-state average from the configured daily change rate. "
        "It does not guarantee the requested RPO during bursts, backlog, or latency events.",
        "Replica storage is reported as the source VM footprint. Extra standard-replication "
        "restore-point delta space is not estimated because replica retention is not an input.",
    ]

    if rin.cdp_enabled:
        if not 2 <= rin.rpo_seconds <= 3600:
            raise ValueError("CDP RPO must be between 2 seconds and 60 minutes.")

        retention_hours = max(0.0, rin.cdp_retention_hours)
        raw_short_term_tb = daily_change_tb * (retention_hours / 24.0)

        # Veeam documents that CDP short-term retention can occupy up to 25% longer than
        # configured because of chain transformations.
        cdp_journal_tb = raw_short_term_tb * 1.25

        if rin.cdp_write_io_mb_s > 0:
            cdp_processing_mb_s = rin.cdp_write_io_mb_s
            processing_basis = "measured vSphere cluster write I/O"
        else:
            cdp_processing_mb_s = required_mb_s
            processing_basis = (
                "average changed-data rate assumption; supply measured cluster write I/O "
                "for production CDP proxy sizing"
            )

        cdp_proxy_count, cdp_proxy_cores, cdp_proxy_ram_gb = _cdp_proxy_resources(
            cdp_processing_mb_s,
            rin.cdp_network_encryption,
        )
        cdp_proxy_cache_gb = 50

        notes.append(
            f"CDP RPO ({rin.rpo_seconds}s) controls restore-point cadence; short-term retention "
            f"is independently modeled from {retention_hours:g} hour(s)."
        )
        notes.append(
            f"Short-term CDP change data is {raw_short_term_tb:.2f} TB; planned capacity is "
            f"{cdp_journal_tb:.2f} TB including Veeam's documented allowance for retention "
            "lasting up to 25% longer during chain transformation."
        )
        notes.append(
            f"CDP proxy sizing uses {processing_basis}. Source and target each require "
            f"{cdp_proxy_count} proxy/proxies at {cdp_proxy_cores} vCPU / "
            f"{cdp_proxy_ram_gb} GB RAM per proxy."
        )
        notes.append(
            "Each CDP proxy is planned with the Veeam-recommended minimum 50 GB disk-based "
            "write-I/O cache."
        )
        if rin.rpo_seconds < 15:
            notes.append(
                "The selected CDP RPO is supported, but Veeam documents 15 seconds or more as "
                "the generally optimal target for higher-write workloads."
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
