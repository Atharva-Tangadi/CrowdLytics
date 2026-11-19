"""Job dispatch, progress polling, cancellation, and results retrieval endpoints."""
import json
import io
import csv
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.entities import AnalysisSession, MediaAsset, AnalysisJob, AnalysisChunk, CrowdAnalysisResult
from app.schemas.api import AnalysisConfigRequest, JobResponse, AnalysisChunkResponse, AnalysisResultResponse
from app.workers.analysis_worker import execute_analysis_job

router = APIRouter(tags=["Analysis"])


@router.get("/sessions/{session_id}/jobs")
def list_session_jobs(session_id: str, db: Session = Depends(get_db)):
    """Keep empty/rejected runs and successful analyses independently accessible."""
    if db.get(AnalysisSession, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    jobs = db.query(AnalysisJob).options(joinedload(AnalysisJob.result)).filter(
        AnalysisJob.session_id == session_id).order_by(AnalysisJob.created_at.desc()).all()
    rows = []
    for job in jobs:
        config = json.loads(job.config_json or '{}')
        summary = json.loads(job.result.summary_data_json or '{}') if job.result else {}
        peak = summary.get('video_analytics',{}).get('peak_count', job.result.total_crowd_count if job.result else None)
        rows.append(dict(JobResponse.model_validate(job).model_dump(),
            confidence_threshold=config.get('confidence_threshold',.3),
            peak_count=peak, result_available=job.result is not None))
    return rows


@router.get("/jobs/{job_id}/results", response_model=Optional[AnalysisResultResponse])
def get_job_results(job_id: str, db: Session = Depends(get_db)):
    if db.get(AnalysisJob, job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return db.query(CrowdAnalysisResult).options(joinedload(CrowdAnalysisResult.groups)).filter(
        CrowdAnalysisResult.job_id == job_id).first()


def analytics_payload(job_id, db):
    from app.cv.analytics import summarize_frames
    job = db.get(AnalysisJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    chunks = db.query(AnalysisChunk).filter(AnalysisChunk.job_id == job_id).order_by(AnalysisChunk.chunk_index).all()
    frames = [frame for chunk in chunks for frame in json.loads(chunk.frame_data_json)]
    return {"job_id":job.id,"media_asset_id":job.media_asset_id,"status":job.status,
            "summary":summarize_frames(frames),"frames":frames}


@router.get("/jobs/{job_id}/analytics")
def get_analytics(job_id: str, db: Session = Depends(get_db)):
    """Stored playback timeline, per-group observations and aggregate occupancy."""
    return analytics_payload(job_id, db)


@router.get("/jobs/{job_id}/analytics/export")
def export_analytics(job_id: str, format: str = Query("json", pattern="^(json|csv)$"), db: Session = Depends(get_db)):
    data = analytics_payload(job_id, db)
    if format == "json":
        return StreamingResponse(iter([json.dumps(data)]), media_type="application/json",
            headers={"Content-Disposition":f'attachment; filename=timeline_{job_id}.json'})
    output = io.StringIO()
    columns = ["timestamp","frame_index","crowd_count","tracked_count","group_id","member_count",
               "centroid_x","centroid_y","motion_speed","speed_unit","direction_label","motion_status",
               "density_per_kpx","mean_nn_distance","observation_status","event_state"]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for frame in data['frames']:
        for group in frame['groups'] or [{}]:
            row = {key:group.get(key,"") for key in columns}
            row.update({key:frame.get(key,"") for key in ("timestamp","frame_index","crowd_count","tracked_count")})
            row.update(centroid_x=group.get('centroid',[None,None])[0],centroid_y=group.get('centroid',[None,None])[1],
                       event_state=frame.get('crowd_event',{}).get('state',''))
            writer.writerow(row)
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",
        headers={"Content-Disposition":f'attachment; filename=timeline_{job_id}.csv'})


@router.post("/sessions/{session_id}/analyze", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def start_analysis_job(
    session_id: str,
    req: AnalysisConfigRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Enqueues an analysis job for a media asset in the local session."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
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

    # Dispatch to asynchronous execution (Celery if configured, otherwise BackgroundTasks)
    import os
    use_celery = os.getenv("USE_CELERY", "false").lower() in ("true", "1")
    dispatched = False
    if use_celery:
        try:
            from app.workers.celery_worker import celery_app, celery_execute_analysis_job
            if celery_app:
                celery_execute_analysis_job.delay(job.id)
                dispatched = True
        except Exception:
            dispatched = False

    if not dispatched:
        background_tasks.add_task(execute_analysis_job, job.id)

    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves progress and status of an analysis job."""
    job = db.query(AnalysisJob).join(AnalysisSession).filter(
        AnalysisJob.id == job_id,
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


@router.get("/jobs/{job_id}/chunks", response_model=list[AnalysisChunkResponse])
def get_job_chunks(
    job_id: str,
    after_index: int = Query(-1, ge=-1),
    db: Session = Depends(get_db)
):
    """Retrieves all completed analysis chunks for progressive video playback."""
    job = db.query(AnalysisJob).join(AnalysisSession).filter(
        AnalysisJob.id == job_id,
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    chunks = db.query(AnalysisChunk).filter(
        AnalysisChunk.job_id == job.id,
        AnalysisChunk.chunk_index > after_index,
        AnalysisChunk.status == "COMPLETED"
    ).order_by(AnalysisChunk.chunk_index.asc()).all()

    return chunks


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Cancels a queued or active job."""
    job = db.query(AnalysisJob).join(AnalysisSession).filter(
        AnalysisJob.id == job_id,
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if job.status in ["COMPLETED", "FAILED"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job is already {job.status}.")

    cancelled = db.query(AnalysisJob).filter(
        AnalysisJob.id == job.id, AnalysisJob.status.in_(["QUEUED", "RUNNING", "CANCELLED"])
    ).update({"status": "CANCELLED", "error_message": "Cancelled by user request."}, synchronize_session=False)
    if not cancelled:
        db.rollback()
        raise HTTPException(status_code=400, detail="Job finished before cancellation.")
    db.commit()
    db.refresh(job)
    return job


@router.get("/sessions/{session_id}/results", response_model=Optional[AnalysisResultResponse])
def get_session_results(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Fetches the latest analysis result for a session, or returns null if not yet analyzed."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
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
    db: Session = Depends(get_db)
):
    """Exports crowd group analysis results as CSV or JSON."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
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
            "motion_angle_deg", "formation_state", "motion_speed", "speed_unit"
        ])
        for g in result.groups:
            writer.writerow([
                g.cluster_id, g.member_count, round(g.centroid_x, 2), round(g.centroid_y, 2),
                round(g.convex_hull_area, 2), round(g.mean_nn_distance, 2), round(g.density_per_kpx, 2),
                round(g.motion_angle_deg, 2) if g.motion_angle_deg is not None else "",
                g.formation_state or "", g.motion_speed if g.motion_speed is not None else "",
                "px/s" if json.loads(result.summary_data_json or "{}").get("annotation_version", 1) >= 2 else "legacy displacement"
            ])
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=crowd_analysis_{session_id}.csv"}
        )

    # Return structured JSON
    return {
        "media_asset_id": result.media_asset_id,
        "analysis_details": json.loads(result.summary_data_json or "{}"),
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
                "motion_speed": g.motion_speed,
                "formation_state": g.formation_state
            }
            for g in result.groups
        ]
    }
