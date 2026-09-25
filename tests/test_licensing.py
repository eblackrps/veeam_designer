from veeam_designer.licensing import estimate_license
from veeam_designer.models import LicenseInput


def test_instance_model_counts_generic_vm_physical_and_cloud_workloads():
    result = estimate_license(
        LicenseInput(
            vm_count=100,
            physical_count=20,
            cloud_workloads=10,
            license_type="instance",
        )
    )

    assert result.tier == "instance"
    assert result.instance_consumption == 130.0
    assert result.protected_workloads == 130
    assert result.annual_maintenance_usd == 0.0


def test_unstructured_instance_consumption_is_one_instance_per_500_gb():
    result = estimate_license(
        LicenseInput(
            vm_count=0,
            nas_tb=50.0,
            license_type="instance",
        )
    )

    assert result.instance_consumption == 100.0
    assert result.protected_workloads == 100


def test_unstructured_instance_consumption_rounds_down_to_500_gb_chunks():
    result = estimate_license(
        LicenseInput(
            vm_count=0,
            nas_tb=1.49,
            license_type="instance",
        )
    )

    assert result.instance_consumption == 2.0


def test_capacity_licensing_rounds_down_to_one_tb_chunks():
    result = estimate_license(
        LicenseInput(
            vm_count=0,
            nas_tb=50.9,
            license_type="capacity",
        )
    )

    assert result.tier == "capacity"
    assert result.capacity_consumption_tb == 50.0


def test_socket_model_requires_supplied_occupied_socket_count():
    unknown = estimate_license(
        LicenseInput(
            vm_count=600,
            license_type="socket",
            occupied_sockets=0,
        )
    )
    supplied = estimate_license(
        LicenseInput(
            vm_count=600,
            license_type="socket",
            occupied_sockets=12,
        )
    )

    assert unknown.estimated_sockets == 0
    assert supplied.estimated_sockets == 12
    assert all("VMs / 10 per socket" not in note for note in supplied.notes)


def test_license_cost_is_never_invented():
    result = estimate_license(LicenseInput(vm_count=1000))

    assert result.annual_maintenance_usd == 0.0
    assert any("pricing is intentionally not estimated" in note for note in result.notes)
