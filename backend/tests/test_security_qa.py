"""Rigorous security and edge-case integration tests."""
import pytest
import numpy as np
import cv2
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal, Base, engine
from app.models.entities import AnalysisSession, MediaAsset, AnalysisJob, CrowdAnalysisResult

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# --- 1. Unauthorized Access & Token Validation ---
def test_unauthorized_endpoints():
    """Verify that unauthenticated requests to protected endpoints return 401."""
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/sessions").status_code == 401
    assert client.post("/api/v1/sessions", json={"title": "Test"}).status_code == 401
    assert client.get("/api/v1/jobs/nonexistent-job-id").status_code == 401
    assert client.get("/api/v1/sessions/nonexistent-session-id/results").status_code == 401


def test_malformed_token_rejection():
    """Verify that forged, malformed, or garbage tokens are rejected."""
    bad_headers = {"Authorization": "Bearer not.a.valid.jwt.token"}
    resp = client.get("/api/v1/sessions", headers=bad_headers)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Could not validate credentials"


# --- 2. Multi-Tenant Cross-User Attack Tests ---
def test_cross_tenant_isolation_and_export_defense():
    """Verify that User B cannot read, download, or export User A's session results."""
    # Register User A & User B
    client.post("/api/v1/auth/register", json={"email": "alice@example.com", "password": "Password123"})
    token_a = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "Password123"}).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    client.post("/api/v1/auth/register", json={"email": "bob@example.com", "password": "Password123"})
    token_b = client.post("/api/v1/auth/login", json={"email": "bob@example.com", "password": "Password123"}).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Alice creates a confidential session
    sess_a = client.post("/api/v1/sessions", json={"title": "Alice Confidential Area"}, headers=headers_a).json()
    session_a_id = sess_a["id"]

    # Bob attempts to get Alice's session -> must return 404
    bob_sess_get = client.get(f"/api/v1/sessions/{session_a_id}", headers=headers_b)
    assert bob_sess_get.status_code == 404

    # Bob attempts to upload media to Alice's session -> must return 404
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, img_encoded = cv2.imencode(".png", img)
    bob_upload = client.post(
        f"/api/v1/sessions/{session_a_id}/media",
        files={"file": ("intruder.png", img_encoded.tobytes(), "image/png")},
        headers=headers_b
    )
    assert bob_upload.status_code == 404

    # Bob attempts to export Alice's results -> must return 404
    bob_export = client.get(f"/api/v1/sessions/{session_a_id}/results/export?format=json", headers=headers_b)
    assert bob_export.status_code == 404

    # Bob attempts to delete Alice's session -> must return 404
    bob_delete = client.delete(f"/api/v1/sessions/{session_a_id}", headers=headers_b)
    assert bob_delete.status_code == 404


# --- 3. Upload Abuse & Corrupted Media Security ---
def test_corrupted_and_empty_media_rejection():
    """Verify that corrupt or zero-byte uploads are cleanly rejected with HTTP 400."""
    client.post("/api/v1/auth/register", json={"email": "media_tester@example.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "media_tester@example.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    session_id = client.post("/api/v1/sessions", json={"title": "Media Test Session"}, headers=headers).json()["id"]

    # 1. Zero-byte file
    empty_resp = client.post(
        f"/api/v1/sessions/{session_id}/media",
        files={"file": ("empty.png", b"", "image/png")},
        headers=headers
    )
    assert empty_resp.status_code == 400
    assert "empty" in empty_resp.json()["detail"].lower()

    # 2. Corrupted file masquerading as PNG
    corrupt_resp = client.post(
        f"/api/v1/sessions/{session_id}/media",
        files={"file": ("fake.png", b"NOT_A_REAL_IMAGE_DATA_12345", "image/png")},
        headers=headers
    )
    assert corrupt_resp.status_code == 400
    assert "corrupted" in corrupt_resp.json()["detail"].lower()

    # 3. Disallowed executable extension masquerading as image
    exe_resp = client.post(
        f"/api/v1/sessions/{session_id}/media",
        files={"file": ("malware.exe", b"MZ_EXE_HEADER", "application/octet-stream")},
        headers=headers
    )
    assert exe_resp.status_code == 400
    assert "unsupported" in exe_resp.json()["detail"].lower()


# --- 4. Cascade Deletion Integrity ---
def test_cascade_deletion():
    """Verify that deleting a session deletes associated media, jobs, and results."""
    client.post("/api/v1/auth/register", json={"email": "cascade@example.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "cascade@example.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    session_id = client.post("/api/v1/sessions", json={"title": "To Delete"}, headers=headers).json()["id"]

    # Upload valid image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.circle(img, (50, 50), 4, (255, 255, 255), -1)
    _, enc = cv2.imencode(".png", img)
    media_id = client.post(
        f"/api/v1/sessions/{session_id}/media",
        files={"file": ("valid.png", enc.tobytes(), "image/png")},
        headers=headers
    ).json()["id"]

    # Launch Analysis
    job_id = client.post(
        f"/api/v1/sessions/{session_id}/analyze",
        json={"media_asset_id": media_id, "confidence_threshold": 0.2, "distance_threshold": 50.0, "linkage_method": "ward"},
        headers=headers
    ).json()["id"]

    # Delete session
    del_resp = client.delete(f"/api/v1/sessions/{session_id}", headers=headers)
    assert del_resp.status_code == 204

    # Verify session is gone
    assert client.get(f"/api/v1/sessions/{session_id}", headers=headers).status_code == 404
    # Verify job is gone
    assert client.get(f"/api/v1/jobs/{job_id}", headers=headers).status_code == 404
