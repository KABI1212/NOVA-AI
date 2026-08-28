from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from main import app
from models.user import User
from utils.dependencies import get_current_user


def test_memory_routes_crud() -> None:
    fake_user = User(id=999, username="mem_tester", email="tester@example.com")

    # Override get_current_user dependency
    app.dependency_overrides[get_current_user] = lambda: fake_user
    client = TestClient(app)

    try:
        # 1. Clear existing
        clear_res = client.delete("/api/memory")
        assert clear_res.status_code == 200

        # 2. Create memory
        create_res = client.post(
            "/api/memory",
            json={"key": "programming_language", "value": "Python 3.12", "category": "preference"},
        )
        assert create_res.status_code == 201
        created_data = create_res.json()
        assert created_data["key"] == "programming_language"
        assert created_data["value"] == "Python 3.12"
        mem_id = created_data["id"]

        # 3. List memories
        list_res = client.get("/api/memory")
        assert list_res.status_code == 200
        items = list_res.json()
        assert any(item["key"] == "programming_language" for item in items)

        # 4. Delete single memory
        del_res = client.delete(f"/api/memory/{mem_id}")
        assert del_res.status_code == 200

    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_memory_multi_tenant_isolation() -> None:
    user_a = User(id=1001, username="user_a", email="usera@example.com")
    user_b = User(id=1002, username="user_b", email="userb@example.com")

    client = TestClient(app)

    try:
        # Step 1: Login as User A and save a preference
        app.dependency_overrides[get_current_user] = lambda: user_a
        client.delete("/api/memory")
        res_a = client.post(
            "/api/memory",
            json={"key": "favorite_language", "value": "Python", "category": "preference"},
        )
        assert res_a.status_code == 201
        mem_a_id = res_a.json()["id"]

        # Step 2: Switch to User B
        app.dependency_overrides[get_current_user] = lambda: user_b
        client.delete("/api/memory")

        # Step 3: User B lists memories -> should NOT see User A's memory
        list_b = client.get("/api/memory")
        assert list_b.status_code == 200
        items_b = list_b.json()
        assert not any(item["key"] == "favorite_language" for item in items_b)

        # Step 4: User B attempts to delete User A's memory ID -> should be 404
        delete_b_attempt = client.delete(f"/api/memory/{mem_a_id}")
        assert delete_b_attempt.status_code == 404

        # Step 5: Switch back to User A -> User A's memory is intact
        app.dependency_overrides[get_current_user] = lambda: user_a
        list_a = client.get("/api/memory")
        assert list_a.status_code == 200
        items_a = list_a.json()
        assert any(item["key"] == "favorite_language" and item["value"] == "Python" for item in items_a)

    finally:
        app.dependency_overrides.pop(get_current_user, None)

