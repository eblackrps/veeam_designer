from veeam_designer.models import VeeamOneInput
from veeam_designer.veeam_one import size_veeam_one


def test_small_deployment():
    vin = VeeamOneInput(protected_vms=100)
    r = size_veeam_one(vin)
    assert r.server_cores == 4
    assert r.server_ram_gb == 8


def test_large_deployment():
    vin = VeeamOneInput(protected_vms=3000)
    r = size_veeam_one(vin)
    assert r.server_cores == 16


def test_enterprise_manager():
    vin = VeeamOneInput(protected_vms=200, enterprise_manager=True)
    r = size_veeam_one(vin)
    assert r.em_cores == 4
    assert r.em_ram_gb == 8


def test_vspc_tenants():
    vin = VeeamOneInput(protected_vms=200, vspc_tenants=150)
    r = size_veeam_one(vin)
    assert r.vspc_cores >= 4
