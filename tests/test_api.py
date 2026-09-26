import pytest

try:
    from fastapi.testclient import TestClient

    from ui.main import app
    from veeam_designer import __version__

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_health_endpoint():
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"] == __version__


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_profiles_endpoint():
    client = TestClient(app)
    r = client.get("/api/profiles")
    assert r.status_code == 200
    data = r.json()
    assert "profiles" in data
    assert isinstance(data["profiles"], list)


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_design_api_basic():
    client = TestClient(app)
    yaml_body = (
        "profile: smb\n"
        "sites:\n"
        "  - name: Test\n"
        "    veeam_input:\n"
        "      total_data_tb: 50\n"
        "      daily_change_percent: 5\n"
        "      backup_window_hours: 8\n"
    )
    r = client.post("/api/design", content=yaml_body, headers={"Content-Type": "text/plain"})
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "multi-site"
    assert data["version"] == __version__
    assert "sites" in data


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_run_page_renders_builder():
    client = TestClient(app)
    r = client.get("/run")
    assert r.status_code == 200
    assert "Veeam Infrastructure Sizing" in r.text
    assert (\n        "Model backup capacity, infrastructure requirements, WAN demand, and storage cost" in r.text\n    )
    assert "Sizing inputs" in r.text
    assert "YAML / API input" in r.text
    assert "Sizing results" in r.text
    assert 'data-platforms="vmware"' in r.text
    assert 'data-workload-scope="vm"' in r.text
    assert '<svg viewBox="0 0 24 24"' in r.text
    assert 'id="runtime-status"' not in r.text
    assert "Browser engine ready." not in r.text


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_export_get_routes_reject_stateful_access():
    client = TestClient(app)

    csv_response = client.get("/export/csv")
    report_response = client.get("/export/report")

    assert csv_response.status_code == 405
    assert report_response.status_code == 405


def test_stateless_csv_export_from_project_body():
    client = TestClient(app)
    yaml_body = (
        "workload_type: vm\n"
        "total_data_tb: 50\n"
        "daily_change_percent: 5\n"
        "backup_window_hours: 8\n"
        "vm_count: 100\n"
        "hypervisor: vmware\n"
    )

    response = client.post(
        "/export/csv",
        content=yaml_body,
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.text.startswith("field,value")


def test_stateless_report_export_from_project_body():
    client = TestClient(app)
    yaml_body = (
        "workload_type: vm\n"
        "total_data_tb: 50\n"
        "daily_change_percent: 5\n"
        "backup_window_hours: 8\n"
        "vm_count: 100\n"
        "hypervisor: vmware\n"
    )

    response = client.post(
        "/export/report",
        content=yaml_body,
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-disposition"].startswith("inline;")
    assert "Infrastructure Sizing Report" in response.text
