"""Background analysis worker running the computer vision pipeline."""
import json
import logging
from datetime import datetime
from typing import Dict, Any
import numpy as np
import cv2

from app.db.session import SessionLocal
from app.models.entities import AnalysisJob, MediaAsset, CrowdAnalysisResult, CrowdGroupSummary
from app.cv.preprocessing.processor import ImagePreprocessor
from app.cv.localization.detector import AerialBlobDensityDetector
from app.cv.clustering.hac import HierarchicalClusterer
from app.cv.closeness.estimator import ClosenessEstimator
from app.cv.motion.analyzer import VideoMotionAnalyzer
from app.cv.formation.tracker import FormationTracker

logger = logging.getLogger("crowdlytics.worker")


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
            # --- Video Analysis ---
            job.current_stage = "Sampling video frames"
            job.progress_pct = 15
            db.commit()

            cap = cv2.VideoCapture(media.storage_path)
            if not cap.isOpened():
                raise ValueError("Failed to open video file.")

            motion_analyzer = VideoMotionAnalyzer()
            formation_tracker = FormationTracker()

            sample_interval = int(config.get("sample_interval_frames", 10))
            frame_idx = 0
            prev_frame = None
            prev_clusters = None
            prev_metrics = None

            sampled_directions = []
            sampled_formations = []
            latest_clustering = None
            latest_closeness = None
            latest_count = 0
            latest_conf = 0.0

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % sample_interval == 0:
                    processed_frame, _ = preprocessor.preprocess(frame)
                    det = detector.detect(processed_frame, confidence_threshold=conf_thresh)
                    clustering = clusterer.cluster(det.points)
                    closeness = closeness_estimator.compute_all(clustering.clusters)

                    latest_clustering = clustering
                    latest_closeness = closeness
                    latest_count = det.total_count
                    latest_conf = det.mean_confidence

                    if prev_frame is not None:
                        # Motion
                        pts_tuples = [(p.x, p.y) for p in det.points]
                        m_res = motion_analyzer.analyze_motion(prev_frame, processed_frame, pts_tuples)
                        if m_res.dominant_direction_deg is not None:
                            sampled_directions.append(m_res.dominant_direction_deg)

                        # Formation
                        if prev_clusters and prev_metrics:
                            f_records = formation_tracker.analyze_temporal_transitions(
                                prev_clusters, prev_metrics, clustering.clusters, closeness.group_metrics
                            )
                            for r in f_records:
                                sampled_formations.append(r.formation_type.value)

                    prev_frame = processed_frame.copy()
                    prev_clusters = clustering.clusters
                    prev_metrics = closeness.group_metrics

                frame_idx += 1
                if frame_idx % 30 == 0:
                    pct = min(15 + int((frame_idx / max(media.frame_count or 100, 1)) * 70), 85)
                    job.progress_pct = pct
                    job.current_stage = f"Analyzing frame {frame_idx}"
                    db.commit()

            cap.release()

            # Aggregate circular mean for video motion
            dominant_dir = None
            if sampled_directions:
                rads = np.radians(sampled_directions)
                dominant_dir = float(np.degrees(np.arctan2(np.sum(np.sin(rads)), np.sum(np.cos(rads)))) % 360.0)

            dom_formation = "stationary"
            if sampled_formations:
                # Majority vote
                from collections import Counter
                dom_formation = Counter(sampled_formations).most_common(1)[0][0]

            job.current_stage = "Finalizing video analysis results"
            job.progress_pct = 90
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
