"""
ObjectFirst Orca appliance sizing module.

Orca specs (as of 2025):
  - 96 TB usable per node
  - 10 GbE connectivity
  - 64 concurrent Veeam streams per node
  - Scale-out cluster supported (≥ 3 nodes recommended for HA)

The calculator mirrors vm.calculator.objectfirst.com and
nas.calculator.objectfirst.com behaviour.
"""

from __future__ import annotations

from math import ceil

from .models import OrcaDesign

ORCA_TB_PER_NODE: float = 96.0
ORCA_STREAMS_PER_NODE: int = 64
ORCA_HA_THRESHOLD: int = 3   # recommend scale-out cluster at this node count


def size_orca(
    total_protected_tb: float,
    immutability_days: int = 30,
    nas_tb: float = 0.0,
) -> OrcaDesign:
    """Size an ObjectFirst Orca cluster for the given protected data volume.

    Args:
        total_protected_tb: Combined primary + GFS repo TB to store on Orca.
        immutability_days:  Immutability lock period in days (adds metadata overhead).
        nas_tb:             Portion of the total that is NAS workload (informational).

    Returns:
        OrcaDesign with node count, usable TB, stream capacity, and guidance notes.
    """
    # Immutability lock keeps extra metadata proportional to the lock window.
    # Minimum 5% overhead; scales at ~20% per year for longer lock windows.
    overhead_factor = 1.0 + max(0.05, (immutability_days / 365.0) * 0.20)
    effective_tb = total_protected_tb * overhead_factor

    node_count = max(1, ceil(effective_tb / ORCA_TB_PER_NODE))
    total_usable_tb = node_count * ORCA_TB_PER_NODE
    concurrent_streams = node_count * ORCA_STREAMS_PER_NODE
    scale_out = node_count >= ORCA_HA_THRESHOLD

    notes: list = []
    if scale_out:
        notes.append(
            f"Scale-out cluster recommended ({node_count} nodes). "
            "Deploy as an ObjectFirst Orca cluster for high-availability."
        )
    if nas_tb > 0:
        nas_pct = (nas_tb / total_protected_tb * 100) if total_protected_tb > 0 else 0
        notes.append(
            f"NAS workload comprises {nas_pct:.0f}% ({nas_tb:.1f} TB) of protected data. "
            "Ensure Veeam NAS backup jobs point to this Orca capacity tier."
        )
    if total_usable_tb - effective_tb < 10:
        notes.append(
            "Available headroom on Orca is < 10 TB. Consider adding one additional node."
        )

    return OrcaDesign(
        node_count=node_count,
        usable_tb_per_node=ORCA_TB_PER_NODE,
        total_usable_tb=round(total_usable_tb, 1),
        concurrent_stream_capacity=concurrent_streams,
        scale_out_recommended=scale_out,
        notes=notes,
    )
