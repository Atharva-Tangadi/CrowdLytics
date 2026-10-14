from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# --- Auth Schemas ---
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Session Schemas ---
class SessionCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Media Schemas ---
class MediaAssetResponse(BaseModel):
    id: str
    session_id: str
    media_type: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    width: Optional[int]
    height: Optional[int]
    duration_seconds: Optional[float]
    fps: Optional[float]
    frame_count: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Analysis & Job Schemas ---
class AnalysisConfigRequest(BaseModel):
    media_asset_id: str
    confidence_threshold: float = Field(0.3, ge=0.05, le=0.95)
    distance_threshold: float = Field(50.0, ge=5.0, le=500.0)
    linkage_method: str = Field("ward", pattern="^(ward|complete|average)$")
    sample_interval_frames: int = Field(5, ge=1, le=60)


class JobResponse(BaseModel):
    id: str
    session_id: str
    media_asset_id: str
    status: str
    progress_pct: int
    current_stage: str
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class AnalysisChunkResponse(BaseModel):
    id: str
    job_id: str
    chunk_index: int
    start_timestamp: float
    end_timestamp: float
    frame_count: int
    status: str
    frame_data_json: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Results Schemas ---
class GroupSummaryResponse(BaseModel):
    id: str
    cluster_id: int
    member_count: int
    centroid_x: float
    centroid_y: float
    bounding_box_json: str
    convex_hull_area: float
    mean_nn_distance: float
    density_per_kpx: float
    motion_angle_deg: Optional[float]
    motion_speed: Optional[float]
    formation_state: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class AnalysisResultResponse(BaseModel):
    id: str
    job_id: str
    total_crowd_count: int
    confidence_score: float
    cluster_count: int
    mean_closeness_px: float
    mean_density_per_kpx: float
    dominant_direction_deg: Optional[float]
    dominant_formation_type: Optional[str]
    summary_data_json: Optional[str]
    groups: List[GroupSummaryResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
