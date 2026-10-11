"""Comprehensive tests for authentication, sessions, media upload, and job lifecycle."""
import io
import pytest
import numpy as np
import cv2
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal, Base, engine
from app.workers.analysis_worker import execute_analysis_job
from app.models.entities import AnalysisJob

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_auth_registration_and_login():
    email = "user1@example.com"
    password = "SuperSecretPassword123"

    # 1. Register
    reg_resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == email

    # Duplicate registration should fail
    dup_resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert dup_resp.status_code == 400

    # 2. Login
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 3. Get Profile
    prof_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert prof_resp.status_code == 200
    assert prof_resp.json()["email"] == email


def test_cross_user_isolation():
    # User A
    client.post("/api/v1/auth/register", json={"email": "usera@example.com", "password": "Password123"})
    token_a = client.post("/api/v1/auth/login", json={"email": "usera@example.com", "password": "Password123"}).json()["access_token"]

    # User B
    client.post("/api/v1/auth/register", json={"email": "userb@example.com", "password": "Password123"})
    token_b = client.post("/api/v1/auth/login", json={"email": "userb@example.com", "password": "Password123"}).json()["access_token"]

    # User A creates a session
    sess_resp = client.post(
        "/api/v1/sessions",
        json={"title": "Session A", "description": "Private to A"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert sess_resp.status_code == 201
    session_a_id = sess_resp.json()["id"]

    # User B attempts to access User A's session -> must return 404
    b_access = client.get(
        f"/api/v1/sessions/{session_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert b_access.status_code == 404


def test_media_upload_and_analysis_pipeline():
    # Register & Login
    client.post("/api/v1/auth/register", json={"email": "tester@example.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "tester@example.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Session
    session_id = client.post("/api/v1/sessions", json={"title": "Crowd Test"}, headers=headers).json()["id"]

    # Generate synthetic image with two distinct groups of people (3 in group A, 3 in group B)
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    # Group A (around 50, 50) - separated by ~15 px
    for (x, y) in [(40, 50), (60, 50), (50, 65)]:
        cv2.circle(img, (x, y), 4, (255, 255, 255), -1)
    # Group B (around 200, 200) - separated by ~15 px
    for (x, y) in [(190, 200), (210, 200), (200, 215)]:
        cv2.circle(img, (x, y), 4, (255, 255, 255), -1)

    _, img_encoded = cv2.imencode(".png", img)
    img_bytes = img_encoded.tobytes()

    # Upload Media
    upload_resp = client.post(
        f"/api/v1/sessions/{session_id}/media",
        files={"file": ("test_aerial.png", img_bytes, "image/png")},
        headers=headers
    )
    assert upload_resp.status_code == 201
    media_data = upload_resp.json()
    media_id = media_data["id"]
    assert media_data["media_type"] == "IMAGE"
    assert media_data["width"] == 300

    # Start Analysis Job
    analyze_resp = client.post(
        f"/api/v1/sessions/{session_id}/analyze",
        json={
            "media_asset_id": media_id,
            "confidence_threshold": 0.2,
            "distance_threshold": 30.0,
            "linkage_method": "ward"
        },
        headers=headers
    )
    assert analyze_resp.status_code == 202
    job_id = analyze_resp.json()["id"]

    # In FastAPI TestClient, background_tasks execute immediately before response completes.
    # Check Job Status
    job_resp = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "COMPLETED"
    assert job_resp.json()["progress_pct"] == 100

    # Fetch Results
    res_resp = client.get(f"/api/v1/sessions/{session_id}/results", headers=headers)
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["total_crowd_count"] >= 2
    assert res_data["cluster_count"] >= 1
    assert len(res_data["groups"]) >= 1

    # Verify JSON and CSV export
    export_json = client.get(f"/api/v1/sessions/{session_id}/results/export?format=json", headers=headers)
    assert export_json.status_code == 200
    assert export_json.json()["session_id"] == session_id

    export_csv = client.get(f"/api/v1/sessions/{session_id}/results/export?format=csv", headers=headers)
    assert export_csv.status_code == 200
    assert "cluster_id,member_count" in export_csv.text
