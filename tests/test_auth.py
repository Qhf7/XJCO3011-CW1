"""Tests for authentication endpoints."""

import pytest


def test_register_success(client):
    resp = client.post("/auth/register", json={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "securepass",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["is_active"] is True
    assert "hashed_password" not in data


def test_register_duplicate_username(client):
    client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup1@example.com",
        "password": "pass12345",
    })
    resp = client.post("/auth/register", json={
        "username": "dupuser",
        "email": "dup2@example.com",
        "password": "pass12345",
    })
    assert resp.status_code == 400
    assert "taken" in resp.json()["detail"].lower()


def test_register_invalid_email(client):
    resp = client.post("/auth/register", json={
        "username": "user_x",
        "email": "not-an-email",
        "password": "pass12345",
    })
    assert resp.status_code == 422


def test_register_short_password(client):
    resp = client.post("/auth/register", json={
        "username": "user_y",
        "email": "y@example.com",
        "password": "short",
    })
    assert resp.status_code == 422


def test_login_success(client):
    client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@example.com",
        "password": "loginpass1",
    })
    resp = client.post("/auth/login", data={
        "username": "loginuser",
        "password": "loginpass1",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/auth/register", json={
        "username": "wrongpass",
        "email": "wp@example.com",
        "password": "correctpass",
    })
    resp = client.post("/auth/login", data={
        "username": "wrongpass",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


def test_protected_route_without_token(client):
    resp = client.post("/ingredients", json={
        "description": "Unauthorized ingredient",
    })
    assert resp.status_code == 401


def test_protected_route_with_token(client, auth_headers):
    resp = client.post("/ingredients", json={
        "description": "Authorized ingredient",
    }, headers=auth_headers)
    assert resp.status_code == 201
