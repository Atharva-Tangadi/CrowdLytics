"""Media asset ingestion and retrieval endpoints."""
from typing import List
from pathlib import Path
from app.core.config import settings
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import AnalysisSession, MediaAsset
from app.storage.service import storage_service
from app.schemas.api import MediaAssetResponse

router = APIRouter(prefix="/sessions", tags=["Media"])


@router.post("/{session_id}/media", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Uploads and validates image or video media into a session."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".avi"}:
        raise HTTPException(status_code=400, detail="Unsupported media extension.")
    limit = (settings.MAX_IMAGE_SIZE_MB if ext in {".jpg", ".jpeg", ".png"}
             else settings.MAX_VIDEO_SIZE_MB) * 1024 * 1024
    contents = bytearray()
    while block := await file.read(1024 * 1024):
        contents.extend(block)
        if len(contents) > limit:
            raise HTTPException(status_code=413, detail="Media exceeds configured size limit.")
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
    db: Session = Depends(get_db)
):
    """Lists media assets in an local session."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    return db.query(MediaAsset).filter(MediaAsset.session_id == session.id).all()


@router.get("/media/{media_id}/file")
def get_media_file(
    media_id: str,
    db: Session = Depends(get_db)
):
    """Securely streams media file from private storage."""
    asset = db.query(MediaAsset).join(AnalysisSession).filter(
        MediaAsset.id == media_id,
    ).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")

    try:
        resolved_path = storage_service.get_file_path(asset.storage_path)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on disk.")

    return FileResponse(path=str(resolved_path), media_type=asset.mime_type)


@router.delete("/{session_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    session_id: str,
    media_id: str,
    db: Session = Depends(get_db)
):
    """Deletes an individual media asset from an local session."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    asset = db.query(MediaAsset).filter(
        MediaAsset.id == media_id,
        MediaAsset.session_id == session.id
    ).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found.")

    storage_service.delete_file(asset.storage_path)
    db.delete(asset)
    db.commit()
    return None

