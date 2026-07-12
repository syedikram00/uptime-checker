from fastapi.testclient import TestClient
from app.main import app, monitors

client = TestClient(app)

def setup_function():
    monitors.clear()

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_add_and_list_monitor():
    response = client.post("/monitors", json={"name": "My Site", "url": "https://example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "My Site"
    assert "id" in data

    list_response = client.get("/monitors")
    assert len(list_response.json()) == 1

def test_get_nonexistent_monitor():
    response = client.get("/monitors/fake-id")
    assert response.status_code == 404

def test_delete_monitor():
    add_response = client.post("/monitors", json={"name": "Temp", "url": "https://example.com"})
    monitor_id = add_response.json()["id"]

    delete_response = client.delete(f"/monitors/{monitor_id}")
    assert delete_response.status_code == 200

    get_response = client.get(f"/monitors/{monitor_id}")
    assert get_response.status_code == 404
