from veeam_designer.models import TapeInput
from veeam_designer.tape import size_tape


def test_lto9_defaults_to_native_capacity_for_backup_data():
    result = size_tape(TapeInput(archive_tb=100.0, lto_generation=9))

    assert result.lto_generation == 9
    assert result.native_tb_per_cartridge == 18.0
    assert result.tb_per_cartridge == 18.0
    assert result.cartridge_count == 6
    assert result.library_slots_needed == 6
    assert result.drive_count_recommended == 1
    assert result.initial_media_cost_usd == 0.0
    assert result.annual_media_cost_usd == 0.0


def test_explicit_media_compression_changes_effective_capacity_only():
    result = size_tape(
        TapeInput(
            archive_tb=100.0,
            lto_generation=9,
            media_compression_ratio=2.5,
        )
    )

    assert result.native_tb_per_cartridge == 18.0
    assert result.tb_per_cartridge == 45.0
    assert result.cartridge_count == 3


def test_media_cost_is_only_calculated_when_user_supplies_price():
    result = size_tape(
        TapeInput(
            archive_tb=100.0,
            lto_generation=9,
            cost_per_cartridge_usd=30.0,
        )
    )

    assert result.cartridge_count == 6
    assert result.initial_media_cost_usd == 180.0
    assert result.annual_media_cost_usd == 0.0


def test_more_data_requires_more_data_cartridges():
    small = size_tape(TapeInput(archive_tb=50.0))
    large = size_tape(TapeInput(archive_tb=500.0))

    assert small.cartridge_count == 3
    assert large.cartridge_count == 28
    assert large.cartridge_count > small.cartridge_count
