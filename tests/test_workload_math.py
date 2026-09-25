from veeam_designer.workload_math import projected_daily_change_tb, projected_total_data_tb


def test_growth_compounds_annually_known_answer():
    assert projected_total_data_tb(100.0, 50.0, 2) == 225.0


def test_zero_year_horizon_does_not_apply_growth():
    assert projected_total_data_tb(100.0, 50.0, 0) == 100.0


def test_projected_daily_change_uses_compounded_protected_size():
    assert projected_daily_change_tb(100.0, 10.0, 50.0, 2) == 22.5
