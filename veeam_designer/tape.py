"""LTO tape archive capacity sizing."""

from __future__ import annotations

from math import ceil

from .models import TapeDesign, TapeInput

LTO_NATIVE_TB: dict[int, float] = {7: 6.0, 8: 12.0, 9: 18.0}


def size_tape(tin: TapeInput) -> TapeDesign:
    """Size data cartridges from native LTO capacity and explicit compression assumptions."""

    notes: list[str] = []
    lto_gen = tin.lto_generation if tin.lto_generation in LTO_NATIVE_TB else 9
    native_tb = LTO_NATIVE_TB[lto_gen]
    compression_ratio = max(1.0, tin.media_compression_ratio)
    effective_tb_per_cart = native_tb * compression_ratio

    data_carts = max(1, ceil(max(0.0, tin.archive_tb) / effective_tb_per_cart))
    library_slots = data_carts

    initial_media_cost = (
        data_carts * max(0.0, tin.cost_per_cartridge_usd)
        if tin.cost_per_cartridge_usd > 0
        else 0.0
    )

    notes.append(
        f"LTO-{lto_gen} is sized at {native_tb:.0f} TB native capacity per cartridge. "
        f"Effective planning capacity is {effective_tb_per_cart:.1f} TB using the supplied "
        f"{compression_ratio:.2f}:1 media-compression ratio."
    )
    if compression_ratio == 1.0:
        notes.append(
            "No additional tape compression is assumed. This is the safe default for Veeam "
            "backup data that may already be compressed."
        )
    else:
        notes.append(
            "Tape compression is workload-dependent. Validate the supplied ratio with real media "
            "usage before purchasing cartridge quantities."
        )
    notes.append(
        "Cartridge and slot counts cover data capacity only. Scratch media, cleaning cartridges, "
        "off-site rotation, and spare slots are operational-policy inputs and are not invented by "
        "the calculator."
    )
    notes.append(
        "Drive count cannot be derived from archive capacity alone. One drive is shown as the "
        "functional minimum; size additional drives from the required tape write/read window."
    )
    if tin.cost_per_cartridge_usd <= 0:
        notes.append("Media pricing is not configured, so no purchase-cost estimate is shown.")

    return TapeDesign(
        cartridge_count=data_carts,
        drive_count_recommended=1,
        library_slots_needed=library_slots,
        lto_generation=lto_gen,
        tb_per_cartridge=round(effective_tb_per_cart, 1),
        annual_media_cost_usd=0.0,
        native_tb_per_cartridge=native_tb,
        initial_media_cost_usd=round(initial_media_cost, 2),
        notes=notes,
    )
