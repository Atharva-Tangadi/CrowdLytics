"""Session management endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.local_workspace import local_owner_id
from app.models.entities import AnalysisSession, MediaAsset
from app.schemas.api import SessionCreateRequest, SessionResponse

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    req: SessionCreateRequest,
    db: Session = Depends(get_db)
):
    """Creates a new analysis session for the local workspace."""
    session = AnalysisSession(
        user_id=local_owner_id(db),
        title=req.title,
        description=req.description
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("", response_model=List[SessionResponse])
def list_sessions(
    db: Session = Depends(get_db)
):
    """Lists all analysis sessions in the local workspace."""
    return db.query(AnalysisSession).order_by(AnalysisSession.created_at.desc()).all()


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves session details in the local workspace."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Deletes an analysis session and cascades media/jobs."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    # Clean up physical media files from disk storage
    media_assets = db.query(MediaAsset).filter(MediaAsset.session_id == session.id).all()
    from app.storage.service import storage_service
    for m in media_assets:
        storage_service.delete_file(m.storage_path)

    db.delete(session)
    db.commit()
    return None
