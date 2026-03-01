from veeam_designer.models import TapeInput
from veeam_designer.tape import size_tape


def test_tape_lto9_basic():
    tin = TapeInput(archive_tb=100.0, lto_generation=9)
    r = size_tape(tin)
    assert r.cartridge_count > 0
    assert r.lto_generation == 9
    assert r.tb_per_cartridge == 45.0


def test_tape_drives_min_2():
    tin = TapeInput(archive_tb=10.0, lto_generation=9)
    r = size_tape(tin)
    assert r.drive_count_recommended >= 2


def test_more_data_more_carts():
    small = size_tape(TapeInput(archive_tb=50.0))
    large = size_tape(TapeInput(archive_tb=500.0))
    assert large.cartridge_count > small.cartridge_count
