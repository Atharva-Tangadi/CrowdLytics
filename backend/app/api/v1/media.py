"""Media asset ingestion and retrieval endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import User, AnalysisSession, MediaAsset
from app.auth.deps import get_current_user
from app.storage.service import storage_service
from app.schemas.api import MediaAssetResponse

router = APIRouter(prefix="/sessions", tags=["Media"])


@router.post("/{session_id}/media", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    session_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Uploads and validates image or video media into a session."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    try:
        storage_path, media_type, file_size, meta = storage_service.save_upload(
            contents, file.filename or "upload.bin"
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))

    asset = MediaAsset(
        session_id=session.id,
        media_type=media_type,
        storage_path=storage_path,
        original_filename=file.filename or "uploaded_media",
        file_size_bytes=file_size,
        mime_type=file.content_type or "application/octet-stream",
        width=meta.get("width"),
        height=meta.get("height"),
        duration_seconds=meta.get("duration_seconds"),
        fps=meta.get("fps"),
        frame_count=meta.get("frame_count")
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/{session_id}/media", response_model=List[MediaAssetResponse])
def list_session_media(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists media assets in an owned session."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    return db.query(MediaAsset).filter(MediaAsset.session_id == session.id).all()


@router.get("/media/{media_id}/file")
def get_media_file(
    media_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Securely streams media file verifying session ownership."""
    asset = db.query(MediaAsset).join(AnalysisSession).filter(
        MediaAsset.id == media_id,
        AnalysisSession.user_id == current_user.id
    ).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")

    try:
        resolved_path = storage_service.get_file_path(asset.storage_path)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on disk.")

    return FileResponse(path=str(resolved_path), media_type=asset.mime_type)
