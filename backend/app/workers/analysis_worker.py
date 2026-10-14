"""Background analysis worker running the computer vision pipeline."""
import json
import logging
from datetime import datetime
from typing import Dict, Any
import numpy as np
import cv2

from app.db.session import SessionLocal
from app.models.entities import AnalysisJob, MediaAsset, AnalysisChunk, CrowdAnalysisResult, CrowdGroupSummary
from app.cv.preprocessing.processor import ImagePreprocessor
from app.cv.localization.detector import AerialBlobDensityDetector
from app.cv.clustering.hac import HierarchicalClusterer
from app.cv.closeness.estimator import ClosenessEstimator
from app.cv.motion.analyzer import VideoMotionAnalyzer
from app.cv.formation.tracker import FormationTracker

logger = logging.getLogger("crowdlytics.worker")


def angle_to_8way_direction(angle_deg: Any, speed: float, min_speed: float = 0.5) -> str:
    """Maps continuous angle [0, 360) in image coordinates to 8-way compass direction."""
    if angle_deg is None or speed < min_speed:
        return "STATIONARY"
    val = (float(angle_deg) + 22.5) % 360.0
    idx = int(val // 45.0)
    directions = [
        "RIGHT",       # ~0 deg (east)
        "DOWN-RIGHT",  # ~45 deg
        "DOWN",        # ~90 deg (south)
        "DOWN-LEFT",   # ~135 deg
        "LEFT",        # ~180 deg (west)
        "UP-LEFT",     # ~225 deg
        "UP",          # ~270 deg (north)
        "UP-RIGHT"     # ~315 deg
    ]
    return directions[idx % 8]


class StableGroupTracker:
    """Tracks crowd groups across frames to maintain stable group identifiers."""

    def __init__(self, max_distance: float = 80.0):
        self.max_distance = max_distance
        self.next_group_id = 1
        self.active_tracks: Dict[int, Dict[str, Any]] = {}

    def assign_ids(self, clusters: list, frame_idx: int) -> list:
        """Assigns stable group IDs based on spatial proximity across sequential frames."""
        if not clusters:
            return []

        assigned_ids = [-1] * len(clusters)
        used_tracks = set()

        for i, c in enumerate(clusters):
            cx, cy = c.centroid
            best_track_id = None
            min_dist = float("inf")

            for track_id, track_info in self.active_tracks.items():
                if track_id in used_tracks:
                    continue
                tx, ty = track_info["centroid"]
                dist = np.hypot(cx - tx, cy - ty)
                if dist < self.max_distance and dist < min_dist:
                    min_dist = dist
                    best_track_id = track_id

            if best_track_id is not None:
                assigned_ids[i] = best_track_id
                used_tracks.add(best_track_id)
                self.active_tracks[best_track_id] = {
                    "centroid": (cx, cy),
                    "size": c.size,
                    "last_seen_frame": frame_idx
                }

        for i, c in enumerate(clusters):
            if assigned_ids[i] == -1:
                new_id = self.next_group_id
                self.next_group_id += 1
                assigned_ids[i] = new_id
                self.active_tracks[new_id] = {
                    "centroid": c.centroid,
                    "size": c.size,
                    "last_seen_frame": frame_idx
                }

        # Expire tracks not seen for > 60 frames
        stale = [tid for tid, info in self.active_tracks.items() if frame_idx - info["last_seen_frame"] > 60]
        for tid in stale:
            del self.active_tracks[tid]

        return assigned_ids


def execute_analysis_job(job_id: str) -> None:
    """Executes crowd analysis asynchronously for an AnalysisJob."""
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job or job.status in ["CANCELLED", "COMPLETED"]:
            return

        # Check if result already exists for this job
        existing_result = db.query(CrowdAnalysisResult).filter(CrowdAnalysisResult.job_id == job_id).first()
        if existing_result:
            return

        job.status = "RUNNING"
        job.started_at = datetime.utcnow()
        job.progress_pct = 5
        job.current_stage = "Loading media asset"
        db.commit()

        media = db.query(MediaAsset).filter(MediaAsset.id == job.media_asset_id).first()
        if not media:
            job.status = "FAILED"
            job.error_message = "Associated media asset not found."
            db.commit()
            return

        config: Dict[str, Any] = json.loads(job.config_json) if job.config_json else {}
        conf_thresh = float(config.get("confidence_threshold", 0.3))
        dist_thresh = float(config.get("distance_threshold", 50.0))
        linkage_method = str(config.get("linkage_method", "ward"))

        preprocessor = ImagePreprocessor()
        detector = AerialBlobDensityDetector()
        clusterer = HierarchicalClusterer(distance_threshold=dist_thresh, linkage_method=linkage_method)
        closeness_estimator = ClosenessEstimator()

        if media.media_type == "IMAGE":
            # --- Image Analysis ---
            job.current_stage = "Preprocessing image"
            job.progress_pct = 20
            db.commit()

            img = cv2.imread(media.storage_path)
            if img is None:
                raise ValueError("Failed to read image from storage.")

            processed_img, scale = preprocessor.preprocess(img)

            job.current_stage = "Localizing crowd members"
            job.progress_pct = 40
            db.commit()

            detection_res = detector.detect(processed_img, confidence_threshold=conf_thresh)

            # Rescale points to original coordinates
            if scale != 1.0 and scale > 0:
                for p in detection_res.points:
                    p.x /= scale
                    p.y /= scale

            job.current_stage = "Performing hierarchical clustering"
            job.progress_pct = 60
            db.commit()

            clustering_res = clusterer.cluster(detection_res.points)

            job.current_stage = "Computing closeness & spatial density"
            job.progress_pct = 80
            db.commit()

            closeness_summary = closeness_estimator.compute_all(clustering_res.clusters)

            # Persist Result
            result = CrowdAnalysisResult(
                job_id=job.id,
                total_crowd_count=detection_res.total_count,
                confidence_score=detection_res.mean_confidence,
                cluster_count=len(clustering_res.clusters),
                mean_closeness_px=closeness_summary.global_mean_nn_distance,
                mean_density_per_kpx=closeness_summary.global_mean_density_per_kpx,
                dominant_direction_deg=None,
                dominant_formation_type=None,
                summary_data_json=json.dumps({
                    "cophenetic_correlation": clustering_res.cophenetic_correlation,
                    "distance_threshold": dist_thresh,
                    "linkage_method": linkage_method,
                    "unclustered_count": len(clustering_res.unclustered_points),
                    "media_type": "IMAGE"
                })
            )
            db.add(result)
            db.flush()

            # Persist Groups
            for c, m in zip(clustering_res.clusters, closeness_summary.group_metrics):
                group = CrowdGroupSummary(
                    result_id=result.id,
                    cluster_id=c.cluster_id,
                    member_count=c.size,
                    centroid_x=c.centroid[0],
                    centroid_y=c.centroid[1],
                    bounding_box_json=json.dumps(c.bounding_box),
                    convex_hull_area=m.convex_hull_area,
                    mean_nn_distance=m.mean_nn_distance,
                    density_per_kpx=m.density_per_kpx,
                    motion_angle_deg=None,
                    motion_speed=None,
                    formation_state=None
                )
                db.add(group)

        else:
            # --- Video Analysis with Progressive Chunk Processing ---
            job.current_stage = "Initializing video stream"
            job.progress_pct = 10
            db.commit()

            cap = cv2.VideoCapture(media.storage_path)
            if not cap.isOpened():
                raise ValueError("Failed to open video file.")

            fps = cap.get(cv2.CAP_PROP_FPS)
            if not fps or fps <= 0 or np.isnan(fps):
                fps = media.fps or 25.0

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                total_frames = media.frame_count or 100

            motion_analyzer = VideoMotionAnalyzer()
            formation_tracker = FormationTracker()
            group_tracker = StableGroupTracker(max_distance=85.0)

            sample_interval = int(config.get("sample_interval_frames", 5))
            chunk_duration_sec = float(config.get("chunk_duration_sec", 2.0))
            chunk_frame_length = max(int(fps * chunk_duration_sec), 15)

            frame_idx = 0
            chunk_index = 0
            current_chunk_start_frame = 0
            chunk_start_timestamp = 0.0
            chunk_frames_data = []

            prev_frame = None
            prev_clusters = None
            prev_metrics = None

            all_sampled_directions = []
            all_sampled_formations = []
            latest_clustering = None
            latest_closeness = None
            latest_count = 0
            latest_conf = 0.0

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % sample_interval == 0:
                    current_timestamp = round(float(frame_idx / fps), 3)
                    processed_frame, scale = preprocessor.preprocess(frame)
                    det = detector.detect(processed_frame, confidence_threshold=conf_thresh)

                    # Rescale detection points to original coordinates if needed
                    if scale != 1.0 and scale > 0:
                        for p in det.points:
                            p.x /= scale
                            p.y /= scale

                    clustering = clusterer.cluster(det.points)
                    closeness = closeness_estimator.compute_all(clustering.clusters)

                    latest_clustering = clustering
                    latest_closeness = closeness
                    latest_count = det.total_count
                    latest_conf = det.mean_confidence

                    # 1. Stable Group ID Tracking
                    stable_ids = group_tracker.assign_ids(clustering.clusters, frame_idx)

                    # 2. Optical Flow & Motion Analysis
                    m_res = None
                    if prev_frame is not None:
                        pts_tuples = [(p.x, p.y) for p in det.points]
                        m_res = motion_analyzer.analyze_motion(prev_frame, processed_frame, pts_tuples)
                        if m_res.dominant_direction_deg is not None:
                            all_sampled_directions.append(m_res.dominant_direction_deg)

                    # 3. Formation Transitions
                    f_record_map = {}
                    if prev_clusters and prev_metrics:
                        f_records = formation_tracker.analyze_temporal_transitions(
                            prev_clusters, prev_metrics, clustering.clusters, closeness.group_metrics
                        )
                        for r in f_records:
                            all_sampled_formations.append(r.formation_type.value)
                            if r.cluster_id is not None:
                                f_record_map[r.cluster_id] = r.formation_type.value

                    # 4. Build Per-Group Annotations for this frame
                    frame_groups_data = []
                    for c_idx, (cluster, metric) in enumerate(zip(clustering.clusters, closeness.group_metrics)):
                        gid = stable_ids[c_idx] if c_idx < len(stable_ids) else (cluster.cluster_id + 1)

                        # Convex Hull vertices
                        pts_arr = np.array([[round(p.x, 1), round(p.y, 1)] for p in cluster.member_points], dtype=np.float32)
                        if len(pts_arr) >= 3:
                            try:
                                hull = cv2.convexHull(pts_arr)
                                hull_coords = [[round(float(pt[0][0]), 1), round(float(pt[0][1]), 1)] for pt in hull]
                            except Exception:
                                hull_coords = [[round(float(p.x), 1), round(float(p.y), 1)] for p in cluster.member_points]
                        else:
                            hull_coords = [[round(float(p.x), 1), round(float(p.y), 1)] for p in cluster.member_points]

                        # Group-level motion: filter vectors belonging to this cluster
                        grp_angle = None
                        grp_speed = 0.0
                        grp_conf = 0.0
                        if m_res and m_res.vectors:
                            bx1, by1, bx2, by2 = cluster.bounding_box
                            matched_vecs = [
                                v for v in m_res.vectors
                                if bx1 - 10 <= v.x <= bx2 + 10 and by1 - 10 <= v.y <= by2 + 10
                            ]
                            if matched_vecs:
                                rads = np.radians([v.angle_degrees for v in matched_vecs])
                                grp_angle = float(np.degrees(np.arctan2(np.sum(np.sin(rads)), np.sum(np.cos(rads)))) % 360.0)
                                grp_speed = float(np.mean([v.magnitude for v in matched_vecs]))
                                grp_conf = float(min(len(matched_vecs) / max(cluster.size, 1), 1.0))
                            elif m_res.dominant_direction_deg is not None:
                                grp_angle = m_res.dominant_direction_deg
                                grp_speed = m_res.mean_speed
                                grp_conf = m_res.confidence * 0.7

                        direction_label = angle_to_8way_direction(grp_angle, grp_speed)
                        formation_state = f_record_map.get(cluster.cluster_id, "stationary")

                        frame_groups_data.append({
                            "group_id": gid,
                            "cluster_id": cluster.cluster_id,
                            "member_count": cluster.size,
                            "centroid": [round(cluster.centroid[0], 1), round(cluster.centroid[1], 1)],
                            "bounding_box": [round(v, 1) for v in cluster.bounding_box],
                            "convex_hull": hull_coords,
                            "mean_nn_distance": round(metric.mean_nn_distance, 1),
                            "density_per_kpx": round(metric.density_per_kpx, 2),
                            "motion_angle_deg": round(grp_angle, 1) if grp_angle is not None else None,
                            "motion_speed": round(grp_speed, 2),
                            "direction_label": direction_label,
                            "motion_confidence": round(grp_conf, 2),
                            "formation_state": formation_state
                        })

                    chunk_frames_data.append({
                        "timestamp": current_timestamp,
                        "frame_index": frame_idx,
                        "crowd_count": det.total_count,
                        "confidence": round(det.mean_confidence, 2),
                        "groups": frame_groups_data
                    })

                    prev_frame = processed_frame.copy()
                    prev_clusters = clustering.clusters
                    prev_metrics = closeness.group_metrics

                frame_idx += 1

                # Check for chunk boundary completion
                if (frame_idx - current_chunk_start_frame >= chunk_frame_length) and chunk_frames_data:
                    chunk_end_timestamp = chunk_frames_data[-1]["timestamp"]
                    chunk = AnalysisChunk(
                        job_id=job.id,
                        chunk_index=chunk_index,
                        start_timestamp=chunk_start_timestamp,
                        end_timestamp=chunk_end_timestamp,
                        frame_count=len(chunk_frames_data),
                        status="COMPLETED",
                        frame_data_json=json.dumps(chunk_frames_data)
                    )
                    db.add(chunk)

                    pct = min(15 + int((frame_idx / max(total_frames, 1)) * 75), 90)
                    job.progress_pct = pct
                    job.current_stage = f"Processed chunk {chunk_index + 1} ({chunk_start_timestamp:.1f}s - {chunk_end_timestamp:.1f}s)"
                    db.commit()

                    chunk_index += 1
                    current_chunk_start_frame = frame_idx
                    chunk_start_timestamp = chunk_end_timestamp
                    chunk_frames_data = []

            cap.release()

            # Finalize remaining frames in last chunk if any
            if chunk_frames_data:
                chunk_end_timestamp = chunk_frames_data[-1]["timestamp"]
                final_chunk = AnalysisChunk(
                    job_id=job.id,
                    chunk_index=chunk_index,
                    start_timestamp=chunk_start_timestamp,
                    end_timestamp=chunk_end_timestamp,
                    frame_count=len(chunk_frames_data),
                    status="COMPLETED",
                    frame_data_json=json.dumps(chunk_frames_data)
                )
                db.add(final_chunk)
                db.commit()
                chunk_index += 1

            # Aggregate circular mean for video motion
            dominant_dir = None
            if all_sampled_directions:
                rads = np.radians(all_sampled_directions)
                dominant_dir = float(np.degrees(np.arctan2(np.sum(np.sin(rads)), np.sum(np.cos(rads)))) % 360.0)

            dom_formation = "stationary"
            if all_sampled_formations:
                from collections import Counter
                dom_formation = Counter(all_sampled_formations).most_common(1)[0][0]

            job.current_stage = "Finalizing video analysis results"
            job.progress_pct = 95
            db.commit()

            result = CrowdAnalysisResult(
                job_id=job.id,
                total_crowd_count=latest_count,
                confidence_score=latest_conf,
                cluster_count=len(latest_clustering.clusters) if latest_clustering else 0,
                mean_closeness_px=latest_closeness.global_mean_nn_distance if latest_closeness else 0.0,
                mean_density_per_kpx=latest_closeness.global_mean_density_per_kpx if latest_closeness else 0.0,
                dominant_direction_deg=dominant_dir,
                dominant_formation_type=dom_formation,
                summary_data_json=json.dumps({
                    "media_type": "VIDEO",
                    "frames_sampled": frame_idx // sample_interval,
                    "chunks_count": chunk_index,
                    "dominant_formation": dom_formation
                })
            )
            db.add(result)
            db.flush()

            if latest_clustering and latest_closeness:
                for c, m in zip(latest_clustering.clusters, latest_closeness.group_metrics):
                    group = CrowdGroupSummary(
                        result_id=result.id,
                        cluster_id=c.cluster_id,
                        member_count=c.size,
                        centroid_x=c.centroid[0],
                        centroid_y=c.centroid[1],
                        bounding_box_json=json.dumps(c.bounding_box),
                        convex_hull_area=m.convex_hull_area,
                        mean_nn_distance=m.mean_nn_distance,
                        density_per_kpx=m.density_per_kpx,
                        motion_angle_deg=dominant_dir,
                        motion_speed=None,
                        formation_state=dom_formation
                    )
                    db.add(group)

        # Complete Job
        job.status = "COMPLETED"
        job.progress_pct = 100
        job.current_stage = "Analysis complete"
        job.completed_at = datetime.utcnow()
        db.commit()

    except Exception as exc:
        logger.exception("Error executing analysis job %s: %s", job_id, exc)
        db.rollback()
        if job:
            job.status = "FAILED"
            job.error_message = str(exc)
            job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
