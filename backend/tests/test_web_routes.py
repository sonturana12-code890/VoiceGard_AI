import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from backend.main import app

def test_routes():
    client = TestClient(app)
    for path in [
        '/', '/app', '/login', '/signup',
        '/style.css', '/landing-and-dashboard.css',
        '/api-client.js', '/landing-controller.js',
        '/app-controller.js', '/script.js'
    ]:
        response = client.get(path)
        assert response.status_code == 200, f"Route {path} failed with {response.status_code}"

    assert client.get('/backend/auth.py').status_code == 404
    assert client.get('/pytest.ini').status_code == 404

