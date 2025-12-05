"""Test suite for key API endpoints."""

from fastapi.testclient import TestClient
import pytest

def test_create_mix(client):
    """Test POST /mixes/create."""
    response = client.post(
        "/mixes/create",
        json={"title": "Test Mix"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Mix"
    assert data["status"] == "draft"
    assert "mix_id" in data

def test_list_mixes(client):
    """Test GET /mixes/ (empty list initially)."""
    response = client.get("/mixes/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_user(client):
    """Test POST /users."""
    response = client.post(
        "/users",
        json={"name": "Test User"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test User"
    assert "id" in data

def test_list_users(client):
    """Test GET /users."""
    response = client.get("/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)