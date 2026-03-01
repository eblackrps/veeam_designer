"""
VM Replication and CDP sizing module.

Mirrors the Veeam Calculator – Machines / VM Replication and CDP Replication tabs.

Standard replication:
  - Bandwidth requirement driven by change rate and RPO window
  - Replica storage = full copy (no compression by default; optional ~10% with compression)

CDP (Continuous Data Protection):
  - Near-zero RPO (target seconds, not hours)
  - Dedicated CDP proxy required (separate from backup proxies)
  - Journal storage: rolling 24-hour window of I/O changes
"""

from __future__ import annotations

from math import ceil

from .models import ReplicationDesign, ReplicationInput


def size_replication(rin: ReplicationInput) -> ReplicationDesign:
    """Size replication infrastructure for the given ReplicationInput."""
    daily_change_tb = rin.source_tb * rin.daily_change_pct / 100.0

    # Data that must transfer within one RPO window
    change_per_rpo_tb = daily_change_tb * (rin.rpo_hours / 24.0)
    window_seconds = rin.rpo_hours * 3600.0
    if window_seconds > 0:
        required_mb_s = (change_per_rpo_tb * 1024.0 * 1024.0) / window_seconds
    else:
        required_mb_s = 0.0

    required_mbps = required_mb_s * 8.0
    meets_rpo = rin.wan_mbps > 0 and required_mbps <= rin.wan_mbps

    # Replica storage: full VM copy on target side.
    # With source-side compression: ~10% smaller than source (0.9×).
    # Without compression: close to source size with ~10% overhead for metadata (1.1×).
    replica_storage_tb = rin.source_tb * (0.9 if rin.compression else 1.1)

    cdp_proxy_cores = 0
    cdp_journal_tb = 0.0

    notes: list = []

    if rin.cdp_enabled:
        # CDP journal: 24 hours of change data per target RPO tier
        # Journal size = daily_change × journal_hours / 24
        journal_hours = max(1.0, rin.rpo_seconds / 3600.0 * 24)
        cdp_journal_tb = daily_change_tb * (journal_hours / 24.0)
        cdp_journal_tb = max(cdp_journal_tb, 0.01)

        # CDP proxies are dedicated — sized by VM density
        cdp_proxy_cores = max(4, ceil(rin.vm_count / 50) * 2)
        notes.append(
            f"CDP proxy required: {cdp_proxy_cores} cores (dedicated, not shared with backup proxies)."
        )
        notes.append(
            f"CDP journal storage: {cdp_journal_tb:.2f} TB "
            f"(rolling {journal_hours:.0f}h window at RPO {rin.rpo_seconds}s)."
        )

    if not meets_rpo and rin.wan_mbps > 0:
        bandwidth_deficit = required_mbps - rin.wan_mbps
        notes.append(
            f"WAN bandwidth insufficient for target RPO {rin.rpo_hours:.1f}h. "
            f"Need {required_mbps:.0f} Mbps, have {rin.wan_mbps:.0f} Mbps "
            f"(deficit {bandwidth_deficit:.0f} Mbps). Consider WAN optimisation or relaxing RPO."
        )
    elif rin.wan_mbps == 0:
        notes.append("No WAN bandwidth specified – RPO feasibility could not be validated.")

    return ReplicationDesign(
        required_mbps=round(required_mbps, 1),
        meets_rpo=meets_rpo,
        replica_storage_tb=round(replica_storage_tb, 1),
        cdp_proxy_cores=cdp_proxy_cores,
        cdp_journal_tb=round(cdp_journal_tb, 2),
        notes=notes,
    )
