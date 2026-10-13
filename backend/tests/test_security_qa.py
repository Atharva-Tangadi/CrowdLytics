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


# --- 5. Worker Failure & Resilience Tests ---
def test_worker_missing_file_failure():
    """Verify worker transitions job to FAILED when media file is missing or unreadable."""
    from app.workers.analysis_worker import execute_analysis_job

    client.post("/api/v1/auth/register", json={"email": "fail_test@example.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "fail_test@example.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    session_id = client.post("/api/v1/sessions", json={"title": "Failure Session"}, headers=headers).json()["id"]

    # Upload valid image first
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, enc = cv2.imencode(".png", img)
    media = client.post(
        f"/api/v1/sessions/{session_id}/media",
        files={"file": ("test.png", enc.tobytes(), "image/png")},
        headers=headers
    ).json()

    # Manually delete media asset from DB to trigger worker failure
    db = SessionLocal()
    job = AnalysisJob(
        session_id=session_id,
        media_asset_id="non-existent-media-uuid",
        status="QUEUED",
        progress_pct=0,
        current_stage="Queued"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    # Run worker directly
    execute_analysis_job(job_id)

    db = SessionLocal()
    updated_job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    assert updated_job.status == "FAILED"
    assert "not found" in updated_job.error_message.lower()
    db.close()


# --- 6. End-to-End Video Analysis Workflow Test ---
def test_video_analysis_pipeline_workflow(tmp_path):
    """Verify video upload, background processing, motion analysis, and formation tracking."""
    client.post("/api/v1/auth/register", json={"email": "video_tester@example.com", "password": "Password123"})
    token = client.post("/api/v1/auth/login", json={"email": "video_tester@example.com", "password": "Password123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    session_id = client.post("/api/v1/sessions", json={"title": "Drone Video Test"}, headers=headers).json()["id"]

    # Create a small synthetic 15-frame video file
    video_path = tmp_path / "synthetic_drone.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 10.0, (200, 200))

    # Moving cluster moving right (+dx per frame)
    for f_idx in range(15):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        # Background reference dots
        cv2.circle(frame, (20, 20), 2, (100, 100, 100), -1)
        cv2.circle(frame, (180, 20), 2, (100, 100, 100), -1)
        cv2.circle(frame, (20, 180), 2, (100, 100, 100), -1)

        # Moving crowd dots
        shift = f_idx * 3
        cv2.circle(frame, (50 + shift, 100), 4, (255, 255, 255), -1)
        cv2.circle(frame, (60 + shift, 105), 4, (255, 255, 255), -1)
        cv2.circle(frame, (55 + shift, 115), 4, (255, 255, 255), -1)
        out.write(frame)
    out.release()

    with open(video_path, "rb") as vf:
        video_bytes = vf.read()

    # Upload Video
    upload_resp = client.post(
        f"/api/v1/sessions/{session_id}/media",
        files={"file": ("synthetic_drone.mp4", video_bytes, "video/mp4")},
        headers=headers
    )
    assert upload_resp.status_code == 201
    media_data = upload_resp.json()
    assert media_data["media_type"] == "VIDEO"
    assert media_data["frame_count"] == 15

    # Run Analysis Job
    analyze_resp = client.post(
        f"/api/v1/sessions/{session_id}/analyze",
        json={
            "media_asset_id": media_data["id"],
            "confidence_threshold": 0.2,
            "distance_threshold": 40.0,
            "linkage_method": "ward",
            "sample_interval_frames": 3
        },
        headers=headers
    )
    assert analyze_resp.status_code == 202
    job_id = analyze_resp.json()["id"]

    # Verify Job Completed
    job_resp = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "COMPLETED"

    # Verify Results contain video motion & formation data
    res_resp = client.get(f"/api/v1/sessions/{session_id}/results", headers=headers)
    assert res_resp.status_code == 200
    res = res_resp.json()
    assert res["total_crowd_count"] >= 1
    assert res["dominant_formation_type"] is not None

