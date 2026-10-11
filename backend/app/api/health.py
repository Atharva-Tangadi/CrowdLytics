"""FastAPI health check router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health/live", status_code=status.HTTP_200_OK)
def liveness():
    """Liveness probe: verifies that the process is running."""
    return {"status": "ok", "service": "crowdlytics-backend", "alive": True}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
def readiness(db: Session = Depends(get_db)):
    """Readiness probe: verifies that database connectivity is functioning."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "service": "crowdlytics-backend",
            "database": "connected"
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connectivity check failed: {str(exc)}"
        )
