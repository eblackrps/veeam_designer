"""LTO tape archive capacity sizing."""

from __future__ import annotations

from math import ceil

from .models import TapeDesign, TapeInput

LTO_NATIVE_TB: dict[int, float] = {7: 6.0, 8: 12.0, 9: 18.0}


def size_tape(tin: TapeInput) -> TapeDesign:
    """Size tape media from native capacity and explicit user assumptions."""

    notes: list[str] = []
    lto_gen = int(tin.lto_generation)

    if tin.native_capacity_tb > 0:
        native_tb = float(tin.native_capacity_tb)
        notes.append(
            f"Native cartridge capacity is explicitly supplied as {native_tb:.1f} TB."
        )
    elif lto_gen in LTO_NATIVE_TB:
        native_tb = LTO_NATIVE_TB[lto_gen]
    elif lto_gen == 10:
        raise ValueError(
            "LTO-10 has both 30 TB and 40 TB native cartridge specifications. "
            "Set native_capacity_tb explicitly."
        )
    else:
        raise ValueError(
            f"No built-in native capacity for LTO-{lto_gen}; set native_capacity_tb explicitly."
        )

    archive_tb = max(0.0, tin.archive_tb)
    compression_ratio = max(1.0, tin.media_compression_ratio)
    effective_tb_per_cart = native_tb * compression_ratio

    data_carts = ceil(archive_tb / effective_tb_per_cart) if archive_tb > 0 else 0
    library_slots = data_carts

    initial_media_cost = (
        data_carts * max(0.0, tin.cost_per_cartridge_usd)
        if tin.cost_per_cartridge_usd > 0
        else 0.0
    )

    required_tape_write_mb_s = 0.0
    drive_count = 1 if data_carts > 0 else 0
    if tin.write_window_hours > 0 and tin.drive_native_mb_s > 0 and archive_tb > 0:
        required_tape_write_mb_s = (
            archive_tb * 1024.0 * 1024.0 / (tin.write_window_hours * 3600.0)
        )
        drive_count = max(1, ceil(required_tape_write_mb_s / tin.drive_native_mb_s))
        notes.append(
            f"Drive count is calculated from the supplied {tin.write_window_hours:g}-hour "
            f"write window and {tin.drive_native_mb_s:g} MB/s per-drive native throughput."
        )
    elif data_carts > 0:
        notes.append(
            "Drive count is shown as one functional minimum because no write window and "
            "per-drive throughput were supplied. Capacity alone cannot determine performance."
        )

    notes.append(
        f"LTO-{lto_gen} media is sized at {native_tb:.1f} TB native per cartridge. "
        f"Effective planning capacity is {effective_tb_per_cart:.1f} TB using the explicit "
        f"{compression_ratio:.2f}:1 media-compression ratio."
    )
    if compression_ratio == 1.0:
        notes.append(
            "No additional tape compression is assumed. This is the safe default for backup "
            "data that may already be compressed."
        )
    else:
        notes.append(
            "Tape compression is workload-dependent; validate the supplied ratio with actual "
            "media usage before purchasing cartridges."
        )

    notes.append(
        "Cartridge and slot counts cover data capacity only. Scratch media, cleaning cartridges, "
        "off-site rotation, GFS media sets, and spare slots are operational-policy inputs and "
        "are not invented by the calculator."
    )
    if tin.cost_per_cartridge_usd <= 0:
        notes.append("Media pricing is not configured, so no purchase-cost estimate is shown.")

    return TapeDesign(
        cartridge_count=data_carts,
        drive_count_recommended=drive_count,
        library_slots_needed=library_slots,
        lto_generation=lto_gen,
        tb_per_cartridge=round(effective_tb_per_cart, 1),
        annual_media_cost_usd=0.0,
        native_tb_per_cartridge=round(native_tb, 1),
        initial_media_cost_usd=round(initial_media_cost, 2),
        required_tape_write_mb_s=round(required_tape_write_mb_s, 1),
        notes=notes,
    )
