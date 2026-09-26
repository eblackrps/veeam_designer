"""Optional Object First appliance capacity helper.

Generic object-storage designs do not call this helper automatically. Current Object First Ootbi
hardware is sold in multiple usable-capacity models, so callers must provide the node capacity
they are actually evaluating rather than relying on a baked-in appliance size.
"""

from __future__ import annotations

from math import ceil

from .models import OrcaDesign


def size_orca(
    total_protected_tb: float,
    usable_tb_per_node: float,
    nas_tb: float = 0.0,
    max_nodes_per_cluster: int = 4,
) -> OrcaDesign:
    """Size an explicitly selected Object First node capacity.

    No extra percentage is added for immutability. The repository engine must already include the
    retention/immutability window in the capacity passed to this helper.
    """

    protected_tb = max(0.0, total_protected_tb)
    node_tb = float(usable_tb_per_node)
    if node_tb <= 0:
        raise ValueError(
            "Object First node capacity must be supplied explicitly; current Ootbi models have "
            "multiple usable-capacity options."
        )

    node_count = max(1, ceil(protected_tb / node_tb))
    total_usable_tb = node_count * node_tb
    max_nodes = max(1, int(max_nodes_per_cluster))
    notes: list[str] = [
        "Node count uses the explicitly supplied usable capacity. Validate the selected current "
        "Ootbi model, performance, and cluster limits against Object First documentation."
    ]

    if node_count > max_nodes:
        notes.append(
            f"{node_count} nodes exceeds the supplied {max_nodes}-node cluster limit; plan "
            "multiple clusters/SOBR extents or select a larger node model."
        )
    if nas_tb > 0:
        nas_pct = (nas_tb / protected_tb * 100.0) if protected_tb > 0 else 0.0
        notes.append(f"NAS workload represents {nas_pct:.0f}% ({nas_tb:.1f} TB) of modeled capacity.")
    if total_usable_tb - protected_tb < node_tb * 0.10:
        notes.append("Less than 10% of one node remains as capacity headroom.")

    return OrcaDesign(
        node_count=node_count,
        usable_tb_per_node=round(node_tb, 1),
        total_usable_tb=round(total_usable_tb, 1),
        concurrent_stream_capacity=0,
        scale_out_recommended=node_count > 1,
        notes=notes,
    )
