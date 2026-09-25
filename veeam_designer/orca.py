"""Object First Ootbi appliance sizing."""

from __future__ import annotations

from math import ceil

from .models import OrcaDesign

OOTBI_NODE_CAPACITIES_TB = (18.0, 36.0, 72.0, 144.0, 216.0, 432.0)


def _auto_node_capacity(required_tb: float) -> float:
    candidates: list[tuple[float, int, float]] = []
    for capacity in OOTBI_NODE_CAPACITIES_TB:
        count = max(1, ceil(required_tb / capacity))
        if count <= 4:
            candidates.append((capacity * count, count, capacity))
    if not candidates:
        return 432.0
    _, _, capacity = min(candidates, key=lambda item: (item[0], item[1]))
    return capacity


def size_orca(
    total_protected_tb: float,
    node_capacity_tb: float = 0.0,
    nas_tb: float = 0.0,
) -> OrcaDesign:
    """Size current Ootbi node capacity without adding synthetic immutability overhead."""

    required_tb = max(0.0, total_protected_tb)
    if node_capacity_tb > 0:
        if node_capacity_tb not in OOTBI_NODE_CAPACITIES_TB:
            raise ValueError(
                "Object First node capacity must be one of 18, 36, 72, 144, 216, or 432 TB"
            )
        selected_capacity = float(node_capacity_tb)
    else:
        selected_capacity = _auto_node_capacity(required_tb)

    node_count = max(1, ceil(required_tb / selected_capacity))
    total_usable_tb = node_count * selected_capacity
    per_node_streams = 0  # Object First publishes ingest/IR limits, not a generic Veeam stream count.
    notes: list[str] = []

    if node_count > 4:
        notes.append(
            f"{required_tb:.1f} TB exceeds a four-node {selected_capacity:.0f} TB Ootbi cluster. "
            "Use multiple Ootbi clusters/SOBR or a different validated node mix."
        )
    else:
        notes.append(
            f"Selected {node_count} x {selected_capacity:.0f} TB Ootbi node(s) for "
            f"{total_usable_tb:.1f} TB usable capacity."
        )

    if node_capacity_tb <= 0:
        notes.append(
            "Node size was auto-selected from current 18/36/72/144/216/432 TB Ootbi SKUs by "
            "minimizing provisioned capacity within a four-node cluster."
        )
    if nas_tb > 0:
        notes.append(f"NAS portion supplied: {nas_tb:.1f} TB.")

    notes.append(
        "No extra immutability percentage is added. The repository requirement already includes "
        "the calculator's retention/immutability capacity model."
    )

    return OrcaDesign(
        node_count=node_count,
        usable_tb_per_node=selected_capacity,
        total_usable_tb=round(total_usable_tb, 1),
        concurrent_stream_capacity=per_node_streams,
        scale_out_recommended=node_count > 1,
        notes=notes,
    )
