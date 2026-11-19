"""Comprehensive tests for local sessions, media upload, and job lifecycle."""
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


def test_auth_routes_removed_and_shared_workspace():
    assert client.get('/api/v1/auth/me').status_code == 404
    assert client.post('/api/v1/auth/login',json={}).status_code == 404
    assert client.post('/api/v1/auth/register',json={}).status_code == 404
    schema = client.get('/api/v1/openapi.json').json()
    assert not schema.get('components',{}).get('securitySchemes')
    assert client.get('/api/v1/sessions').json() == []


def test_sessions_shared_between_local_clients():
    session = client.post('/api/v1/sessions',json={'title':'Shared local analysis'}).json()
    other = TestClient(app)
    assert other.get(f'/api/v1/sessions/{session["id"]}').status_code == 200
    assert session['id'] in [s['id'] for s in other.get('/api/v1/sessions').json()]


def test_media_upload_and_analysis_pipeline():
    # No credentials are needed for local access.
    headers = {}

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


def test_job_cancellation():
    """Verify that a queued or running job can be cancelled."""
    headers = {}

    sess_id = client.post("/api/v1/sessions", json={"title": "Cancel Test"}, headers=headers).json()["id"]

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, enc = cv2.imencode(".png", img)
    media_id = client.post(
        f"/api/v1/sessions/{sess_id}/media",
        files={"file": ("test.png", enc.tobytes(), "image/png")},
        headers=headers
    ).json()["id"]

    # Create job directly in DB as QUEUED to test cancel without background race
    db = SessionLocal()
    job = AnalysisJob(session_id=sess_id, media_asset_id=media_id, status="QUEUED", progress_pct=0, current_stage="Queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    cancel_resp = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"


def test_delete_individual_media_asset():
    """Verify deleting an individual media asset cleans up DB and disk storage."""
    headers = {}

    sess_id = client.post("/api/v1/sessions", json={"title": "Delete Media Test"}, headers=headers).json()["id"]

    img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, enc = cv2.imencode(".png", img)
    media_resp = client.post(
        f"/api/v1/sessions/{sess_id}/media",
        files={"file": ("temp.png", enc.tobytes(), "image/png")},
        headers=headers
    )
    media_id = media_resp.json()["id"]

    # Delete media asset
    del_resp = client.delete(f"/api/v1/sessions/{sess_id}/media/{media_id}", headers=headers)
    assert del_resp.status_code == 204

    # Verify media asset is no longer listed
    list_resp = client.get(f"/api/v1/sessions/{sess_id}/media", headers=headers)
    assert len(list_resp.json()) == 0

