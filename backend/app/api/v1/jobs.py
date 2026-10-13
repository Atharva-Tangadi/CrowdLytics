"""Job dispatch, progress polling, cancellation, and results retrieval endpoints."""
import json
import io
import csv
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.entities import User, AnalysisSession, MediaAsset, AnalysisJob, CrowdAnalysisResult
from app.auth.deps import get_current_user
from app.schemas.api import AnalysisConfigRequest, JobResponse, AnalysisResultResponse
from app.workers.analysis_worker import execute_analysis_job

router = APIRouter(tags=["Analysis"])


@router.post("/sessions/{session_id}/analyze", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def start_analysis_job(
    session_id: str,
    req: AnalysisConfigRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enqueues an analysis job for a media asset in the user's session."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    media = db.query(MediaAsset).filter(
        MediaAsset.id == req.media_asset_id,
        MediaAsset.session_id == session.id
    ).first()
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found in this session.")

    job = AnalysisJob(
        session_id=session.id,
        media_asset_id=media.id,
        status="QUEUED",
        progress_pct=0,
        current_stage="Job queued",
        config_json=json.dumps(req.model_dump())
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch to background task execution
    background_tasks.add_task(execute_analysis_job, job.id)

    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves progress and status of an analysis job."""
    job = db.query(AnalysisJob).join(AnalysisSession).filter(
        AnalysisJob.id == job_id,
        AnalysisSession.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancels a queued or active job."""
    job = db.query(AnalysisJob).join(AnalysisSession).filter(
        AnalysisJob.id == job_id,
        AnalysisSession.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if job.status in ["COMPLETED", "FAILED"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job is already {job.status}.")

    job.status = "CANCELLED"
    job.error_message = "Cancelled by user request."
    db.commit()
    db.refresh(job)
    return job


@router.get("/sessions/{session_id}/results", response_model=Optional[AnalysisResultResponse])
def get_session_results(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetches the latest analysis result for a session, or returns null if not yet analyzed."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    result = db.query(CrowdAnalysisResult).join(AnalysisJob).options(
        joinedload(CrowdAnalysisResult.groups)
    ).filter(
        AnalysisJob.session_id == session.id
    ).order_by(CrowdAnalysisResult.created_at.desc()).first()

    return result


@router.get("/sessions/{session_id}/results/export")
def export_results(
    session_id: str,
    format: str = "json",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Exports crowd group analysis results as CSV or JSON."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    result = db.query(CrowdAnalysisResult).join(AnalysisJob).options(
        joinedload(CrowdAnalysisResult.groups)
    ).filter(
        AnalysisJob.session_id == session.id
    ).order_by(CrowdAnalysisResult.created_at.desc()).first()

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No results found to export.")

    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "cluster_id", "member_count", "centroid_x", "centroid_y",
            "convex_hull_area_sq_px", "mean_nn_distance_px", "density_per_kpx",
            "motion_angle_deg", "formation_state"
        ])
        for g in result.groups:
            writer.writerow([
                g.cluster_id, g.member_count, round(g.centroid_x, 2), round(g.centroid_y, 2),
                round(g.convex_hull_area, 2), round(g.mean_nn_distance, 2), round(g.density_per_kpx, 2),
                round(g.motion_angle_deg, 2) if g.motion_angle_deg is not None else "",
                g.formation_state or ""
            ])
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=crowd_analysis_{session_id}.csv"}
        )

    # Return structured JSON
    return {
        "session_id": session.id,
        "session_title": session.title,
        "total_crowd_count": result.total_crowd_count,
        "confidence_score": result.confidence_score,
        "cluster_count": result.cluster_count,
        "mean_closeness_px": result.mean_closeness_px,
        "mean_density_per_kpx": result.mean_density_per_kpx,
        "dominant_direction_deg": result.dominant_direction_deg,
        "dominant_formation_type": result.dominant_formation_type,
        "groups": [
            {
                "cluster_id": g.cluster_id,
                "member_count": g.member_count,
                "centroid": [g.centroid_x, g.centroid_y],
                "convex_hull_area": g.convex_hull_area,
                "mean_nn_distance": g.mean_nn_distance,
                "density_per_kpx": g.density_per_kpx,
                "motion_angle_deg": g.motion_angle_deg,
                "formation_state": g.formation_state
            }
            for g in result.groups
        ]
    }
