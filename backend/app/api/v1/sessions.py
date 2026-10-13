"""Session management endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import User, AnalysisSession, MediaAsset
from app.auth.deps import get_current_user
from app.schemas.api import SessionCreateRequest, SessionResponse

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    req: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Creates a new analysis session for the authenticated user."""
    session = AnalysisSession(
        user_id=current_user.id,
        title=req.title,
        description=req.description
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("", response_model=List[SessionResponse])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all analysis sessions owned by the authenticated user."""
    return db.query(AnalysisSession).filter(AnalysisSession.user_id == current_user.id).order_by(AnalysisSession.created_at.desc()).all()


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves session details ensuring user ownership."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deletes an analysis session and cascades media/jobs."""
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == current_user.id
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
