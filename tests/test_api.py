import pytest

try:
    from fastapi.testclient import TestClient
    from ui.main import app
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
    assert data["version"] == "3.0.0"


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
    assert "sites" in data
