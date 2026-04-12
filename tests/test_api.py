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
    assert "Interactive design composer" in r.text
    assert "Live YAML workspace" in r.text


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_export_csv_requires_result():
    client = TestClient(app)
    r = client.get("/export/csv")
    assert r.status_code == 400
