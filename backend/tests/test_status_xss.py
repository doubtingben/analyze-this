
import pytest
from fastapi.testclient import TestClient
from main import app, SECRET_KEY, CSRF_KEY

# Mocking auth
def mock_auth_headers():
    return {"Authorization": "Bearer dev-token"}

def test_update_item_status_xss():
    with TestClient(app) as client:
        # 1. Create an item using JSON
        response = client.post(
            "/api/share",
            json={"title": "Test Item", "content": "Test Content", "type": "text"},
            headers=mock_auth_headers()
        )
        if response.status_code != 200:
            print(f"Creation failed: {response.text}")
        assert response.status_code == 200

        data = response.json()
        item_id = data.get("id") or data.get("firestore_id")

        # 2. Update status with XSS payload
        xss_payload = "<img src=x onerror=alert(1)>"
        response = client.patch(
            f"/api/items/{item_id}",
            json={"status": xss_payload},
            headers=mock_auth_headers()
        )

        # New behavior: Should be 422 Unprocessable Entity
        print(f"Update response status: {response.status_code}")
        print(f"Update response body: {response.text}")

        assert response.status_code == 422

        # 3. Verify it was NOT updated
        get_resp = client.get("/api/items", headers=mock_auth_headers())
        items = get_resp.json()
        target_item = next(i for i in items if (i.get("firestore_id") == item_id or i.get("id") == item_id))
        assert target_item["status"] != xss_payload
        assert target_item["status"] == "new" # Default

if __name__ == "__main__":
    test_update_item_status_xss()
