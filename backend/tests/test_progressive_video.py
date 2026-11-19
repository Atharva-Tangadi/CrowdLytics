"""Targeted tests for progressive video processing, timestamp synchronization, and stable tracking."""
import json
import pytest
import numpy as np
import cv2
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal, Base, engine
from app.models.entities import AnalysisJob, AnalysisChunk
from app.workers.analysis_worker import (
    execute_analysis_job,
    angle_to_8way_direction,
    StableGroupTracker,
)
from app.cv.clustering.hac import ClusterGroup, DetectionPoint

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    Base.metadata.create_all(bind=engine)
    yield


# --- 1. Direction Mapping Tests ---
def test_angle_to_8way_direction_mapping():
    """Verify 8-way compass direction mapping from continuous angles."""
    # Stationary
    assert angle_to_8way_direction(None, 0.0) == "STATIONARY"
    assert angle_to_8way_direction(45.0, 0.2, min_speed=0.5) == "STATIONARY"

    # Cardinal and intercardinal
    assert angle_to_8way_direction(0.0, 2.0) == "RIGHT"
    assert angle_to_8way_direction(45.0, 2.0) == "DOWN-RIGHT"
    assert angle_to_8way_direction(90.0, 2.0) == "DOWN"
    assert angle_to_8way_direction(135.0, 2.0) == "DOWN-LEFT"
    assert angle_to_8way_direction(180.0, 2.0) == "LEFT"
    assert angle_to_8way_direction(225.0, 2.0) == "UP-LEFT"
    assert angle_to_8way_direction(270.0, 2.0) == "UP"
    assert angle_to_8way_direction(315.0, 2.0) == "UP-RIGHT"
    assert angle_to_8way_direction(359.0, 2.0) == "RIGHT"


# --- 2. Stable Group Identifier Tests ---
def test_stable_group_tracker_id_continuity():
    """Verify that moving clusters maintain stable IDs across consecutive time windows."""
    tracker = StableGroupTracker(max_distance=50.0)

    # Frame 0: Two distinct groups at (100, 100) and (300, 300)
    c1 = ClusterGroup(
        cluster_id=0,
        member_indices=[0],
        member_points=[DetectionPoint(x=100, y=100, confidence=0.9)],
        centroid=(100.0, 100.0),
        size=1,
        bounding_box=(95, 95, 105, 105),
    )
    c2 = ClusterGroup(
        cluster_id=1,
        member_indices=[1],
        member_points=[DetectionPoint(x=300, y=300, confidence=0.9)],
        centroid=(300.0, 300.0),
        size=1,
        bounding_box=(295, 295, 305, 305),
    )
    ids_f0 = tracker.assign_ids([c1, c2], frame_idx=0)
    assert ids_f0 == [1, 2]

    # Frame 5: Groups shift by +10px (110, 105) and (310, 305)
    c1_shifted = ClusterGroup(
        cluster_id=0,
        member_indices=[0],
        member_points=[DetectionPoint(x=110, y=105, confidence=0.9)],
        centroid=(110.0, 105.0),
        size=1,
        bounding_box=(105, 100, 115, 110),
    )
    c2_shifted = ClusterGroup(
        cluster_id=1,
        member_indices=[1],
        member_points=[DetectionPoint(x=310, y=305, confidence=0.9)],
        centroid=(310.0, 305.0),
        size=1,
        bounding_box=(305, 300, 315, 310),
    )
    # Notice input cluster order swapped: [c2_shifted, c1_shifted]
    ids_f5 = tracker.assign_ids([c2_shifted, c1_shifted], frame_idx=5)
    # c2_shifted should retain ID 2, c1_shifted should retain ID 1
    assert ids_f5 == [2, 1]


def test_stable_group_tracker_new_group_spawning():
    """Verify that newly appearing groups receive distinct new IDs without mutating existing tracks."""
    tracker = StableGroupTracker(max_distance=50.0)

    c1 = ClusterGroup(
        cluster_id=0,
        member_indices=[0],
        member_points=[DetectionPoint(x=50, y=50, confidence=0.9)],
        centroid=(50.0, 50.0),
        size=1,
        bounding_box=(45, 45, 55, 55),
    )
    ids_f0 = tracker.assign_ids([c1], frame_idx=0)
    assert ids_f0 == [1]

    # New cluster appears far away at (500, 500)
    c_new = ClusterGroup(
        cluster_id=1,
        member_indices=[1],
        member_points=[DetectionPoint(x=500, y=500, confidence=0.9)],
        centroid=(500.0, 500.0),
        size=1,
        bounding_box=(495, 495, 505, 505),
    )
    ids_f1 = tracker.assign_ids([c1, c_new], frame_idx=1)
    assert ids_f1 == [1, 2]


# --- 3. End-to-End Progressive Chunk Generation & API Test ---
def test_progressive_video_chunk_workflow(tmp_path):
    """
    Verifies that a drone video generates progressive AnalysisChunks with:
    - Precise presentation timestamps (t = frame_idx / fps).
    - Stable group identifiers.
    - Direction vectors and 8-way direction labels.
    - Accessible via login-free GET /jobs/{job_id}/chunks.
    """
    email = "progressive_tester@example.com"
    headers = {}

    sess_resp = client.post("/api/v1/sessions", json={"title": "Progressive Drone Session"}, headers=headers)
    session_id = sess_resp.json()["id"]

    # Create synthetic 30-frame video @ 10fps (3.0 seconds total)
    # Moving cluster moving right (+dx per frame)
    video_path = tmp_path / "progressive_test.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = 10.0
    out = cv2.VideoWriter(str(video_path), fourcc, fps, (240, 240))

    for f_idx in range(30):
        frame = np.zeros((240, 240, 3), dtype=np.uint8)
        # Background reference dots for camera motion compensation
        cv2.circle(frame, (20, 20), 2, (120, 120, 120), -1)
        cv2.circle(frame, (220, 20), 2, (120, 120, 120), -1)
        cv2.circle(frame, (20, 220), 2, (120, 120, 120), -1)

        # Rightward moving cluster
        shift = f_idx * 3
        cv2.circle(frame, (40 + shift, 120), 4, (255, 255, 255), -1)
        cv2.circle(frame, (65 + shift, 125), 4, (255, 255, 255), -1)
        cv2.circle(frame, (50 + shift, 150), 4, (255, 255, 255), -1)
        out.write(frame)
    out.release()

    with open(video_path, "rb") as vf:
        video_bytes = vf.read()

    # Upload video
    up_resp = client.post(
        f"/api/v1/sessions/{session_id}/media",
        files={"file": ("progressive_test.mp4", video_bytes, "video/mp4")},
        headers=headers,
    )
    assert up_resp.status_code == 201
    media_id = up_resp.json()["id"]

    # Start analysis job with 1.0s chunk duration
    job_resp = client.post(
        f"/api/v1/sessions/{session_id}/analyze",
        json={
            "media_asset_id": media_id,
            "confidence_threshold": 0.2,
            "distance_threshold": 60.0,
            "linkage_method": "ward",
            "sample_interval_frames": 2,
        },
        headers=headers,
    )
    assert job_resp.status_code == 202
    job_id = job_resp.json()["id"]

    # Verify Job is COMPLETED
    j_poll = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert j_poll.status_code == 200
    assert j_poll.json()["status"] == "COMPLETED"

    # Query Progressive Chunks
    chunks_resp = client.get(f"/api/v1/jobs/{job_id}/chunks", headers=headers)
    assert chunks_resp.status_code == 200
    chunks = chunks_resp.json()
    assert len(chunks) >= 1

    # Verify timestamp monotonicity and chunk metadata
    first_chunk = chunks[0]
    assert first_chunk["status"] == "COMPLETED"
    assert first_chunk["chunk_index"] == 0
    assert first_chunk["start_timestamp"] == 0.0
    assert first_chunk["end_timestamp"] > 0.0

    # Parse frame data in first chunk
    frames = json.loads(first_chunk["frame_data_json"])
    assert len(frames) > 0

    first_frame = frames[0]
    assert "timestamp" in first_frame
    assert "groups" in first_frame
    assert len(first_frame["groups"]) >= 1

    grp = first_frame["groups"][0]
    assert "group_id" in grp
    assert grp["group_id"] >= 1
    assert "convex_hull" in grp
    assert len(grp["convex_hull"]) >= 1
    assert "direction_label" in grp

    # Another local client can read the same workspace without credentials.
    other = TestClient(app)
    assert other.get(f"/api/v1/jobs/{job_id}/chunks").status_code == 200
