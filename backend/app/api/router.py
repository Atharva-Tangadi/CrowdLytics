"""API router aggregating v1 routes."""
from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.media import router as media_router
from app.api.v1.jobs import router as jobs_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(sessions_router)
api_router.include_router(media_router)
api_router.include_router(jobs_router)
