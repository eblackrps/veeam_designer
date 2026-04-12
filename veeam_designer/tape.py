"""LTO tape library / archive tier sizing."""

from __future__ import annotations

from math import ceil

from .models import TapeDesign, TapeInput

LTO_COMPRESSED_TB: dict[int, float] = {7: 15.0, 8: 30.0, 9: 45.0}
COST_PER_CART: dict[int, float] = {7: 20.0, 8: 25.0, 9: 35.0}


def size_tape(tin: TapeInput) -> TapeDesign:
    """Size LTO tape library for archive tier."""
    notes = []
    lto_gen = tin.lto_generation if tin.lto_generation in LTO_COMPRESSED_TB else 9
    tb_per_cart = LTO_COMPRESSED_TB[lto_gen]
    cost_per = COST_PER_CART[lto_gen]

    data_carts = max(1, ceil(tin.archive_tb / tb_per_cart))
    scratch = max(1, ceil(data_carts * 0.2))
    total_carts = data_carts + scratch
    slots = ceil(total_carts * 1.5)
    drives = max(2, ceil(slots / 30))
    annual_media_cost = round(scratch * cost_per, 2)

    notes.append(f"LTO-{lto_gen}: {tb_per_cart:.0f} TB compressed per cartridge.")
    notes.append(f"{data_carts} data cartridges + {scratch} scratch = {total_carts} total.")
    if tin.retention_years > 10:
        notes.append(
            "Long retention (>10 yrs) — verify LTO drive availability for future restores."
        )
    if drives > 4:
        notes.append(f"{drives} drives recommended — consider a modular library chassis.")

    return TapeDesign(
        cartridge_count=total_carts,
        drive_count_recommended=drives,
        library_slots_needed=slots,
        lto_generation=lto_gen,
        tb_per_cartridge=tb_per_cart,
        annual_media_cost_usd=annual_media_cost,
        notes=notes,
    )
