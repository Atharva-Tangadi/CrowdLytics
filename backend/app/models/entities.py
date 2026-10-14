"""SQLAlchemy ORM models for Aerial Crowd Intelligence."""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from app.db.session import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sessions = relationship("AnalysisSession", back_populates="user", cascade="all, delete-orphan")


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")
    media_assets = relationship("MediaAsset", back_populates="session", cascade="all, delete-orphan")
    jobs = relationship("AnalysisJob", back_populates="session", cascade="all, delete-orphan")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    media_type = Column(String(20), nullable=False)  # 'IMAGE' or 'VIDEO'
    storage_path = Column(String(512), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    fps = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("AnalysisSession", back_populates="media_assets")
    jobs = relationship("AnalysisJob", back_populates="media_asset", cascade="all, delete-orphan")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    media_asset_id = Column(String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="QUEUED", nullable=False, index=True)  # QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    progress_pct = Column(Integer, default=0, nullable=False)
    current_stage = Column(String(100), default="Initialized", nullable=False)
    error_message = Column(Text, nullable=True)
    config_json = Column(Text, nullable=True)  # JSON-encoded parameters
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    session = relationship("AnalysisSession", back_populates="jobs")
    media_asset = relationship("MediaAsset", back_populates="jobs")
    result = relationship("CrowdAnalysisResult", back_populates="job", uselist=False, cascade="all, delete-orphan")
    chunks = relationship("AnalysisChunk", back_populates="job", cascade="all, delete-orphan", order_by="AnalysisChunk.chunk_index")


class AnalysisChunk(Base):
    __tablename__ = "analysis_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False, index=True)
    start_timestamp = Column(Float, nullable=False)
    end_timestamp = Column(Float, nullable=False)
    frame_count = Column(Integer, nullable=False, default=0)
    status = Column(String(20), default="COMPLETED", nullable=False)
    frame_data_json = Column(Text, nullable=False)  # JSON-encoded array of per-frame analysis
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("AnalysisJob", back_populates="chunks")


class CrowdAnalysisResult(Base):
    __tablename__ = "crowd_analysis_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    total_crowd_count = Column(Integer, nullable=False)
    confidence_score = Column(Float, nullable=False)
    cluster_count = Column(Integer, nullable=False)
    mean_closeness_px = Column(Float, nullable=False)
    mean_density_per_kpx = Column(Float, nullable=False)
    dominant_direction_deg = Column(Float, nullable=True)
    dominant_formation_type = Column(String(50), nullable=True)
    summary_data_json = Column(Text, nullable=True)  # Full aggregate metrics & details
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("AnalysisJob", back_populates="result")
    groups = relationship("CrowdGroupSummary", back_populates="result", cascade="all, delete-orphan")


class CrowdGroupSummary(Base):
    __tablename__ = "crowd_group_summaries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    result_id = Column(String(36), ForeignKey("crowd_analysis_results.id", ondelete="CASCADE"), nullable=False, index=True)
    cluster_id = Column(Integer, nullable=False)
    member_count = Column(Integer, nullable=False)
    centroid_x = Column(Float, nullable=False)
    centroid_y = Column(Float, nullable=False)
    bounding_box_json = Column(String(255), nullable=False)
    convex_hull_area = Column(Float, nullable=False)
    mean_nn_distance = Column(Float, nullable=False)
    density_per_kpx = Column(Float, nullable=False)
    motion_angle_deg = Column(Float, nullable=True)
    motion_speed = Column(Float, nullable=True)
    formation_state = Column(String(50), nullable=True)

    result = relationship("CrowdAnalysisResult", back_populates="groups")
