from veeam_designer.models import VeeamOneInput
from veeam_designer.veeam_one import size_veeam_one


def test_small_backup_data_deployment_uses_all_in_one_minimums():
    result = size_veeam_one(
        VeeamOneInput(
            protected_vms=100,
            connected_vbr_servers=0,
        )
    )

    assert result.server_cores == 4.0
    assert result.server_ram_gb == 8.0
    assert result.database_size_gb == 0


def test_connected_vbr_overhead_is_preserved_fractionally():
    result = size_veeam_one(
        VeeamOneInput(
            protected_vms=100,
            connected_vbr_servers=1,
        )
    )

    assert result.server_cores == 4.03
    assert result.server_ram_gb == 8.06


def test_3000_workloads_use_upper_end_of_current_backup_data_band():
    result = size_veeam_one(
        VeeamOneInput(
            protected_vms=3000,
            connected_vbr_servers=0,
        )
    )

    assert result.server_cores == 4.0
    assert result.server_ram_gb == 15.0


def test_15000_workloads_use_10k_to_20k_band():
    result = size_veeam_one(
        VeeamOneInput(
            protected_vms=15000,
            connected_vbr_servers=0,
        )
    )

    assert result.server_cores == 6.0
    assert result.server_ram_gb == 30.0


def test_enterprise_manager_uses_recommended_linux_appliance_resources():
    result = size_veeam_one(
        VeeamOneInput(
            protected_vms=200,
            enterprise_manager=True,
            connected_vbr_servers=0,
        )
    )

    assert result.em_cores == 4
    assert result.em_ram_gb == 16


def test_vspc_is_not_sized_from_tenant_count():
    result = size_veeam_one(
        VeeamOneInput(
            protected_vms=200,
            vspc_tenants=150,
            connected_vbr_servers=0,
        )
    )

    assert result.vspc_cores == 0
    assert any("separate product" in note for note in result.notes)


def test_database_capacity_defers_to_veeam_one_database_calculator():
    result = size_veeam_one(
        VeeamOneInput(
            protected_vms=5000,
            retention_days=365,
            connected_vbr_servers=0,
        )
    )

    assert result.database_size_gb == 0
    assert any("Database Calculator" in note for note in result.notes)
