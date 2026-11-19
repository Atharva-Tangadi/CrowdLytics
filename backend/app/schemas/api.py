from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


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
class CrowdIncreaseConfig(BaseModel):
    enabled: bool = True
    window_seconds: float = Field(10., ge=2, le=120)
    min_history_seconds: float = Field(3., ge=0.5, le=60)
    min_samples: int = Field(5, ge=2, le=100)
    min_absolute: int = Field(15, ge=1, le=10000)
    min_percent: float = Field(50., ge=0, le=10000)
    mad_multiplier: float = Field(3., ge=0, le=20)
    persistence_seconds: float = Field(1., ge=0, le=30)
    cooldown_seconds: float = Field(10., ge=0, le=300)
    max_gap_seconds: float = Field(3., ge=0.1, le=60)

    @model_validator(mode="after")
    def validate_window(self):
        if self.min_history_seconds >= self.window_seconds:
            raise ValueError("Baseline window must exceed minimum history duration")
        return self


class AnalysisConfigRequest(BaseModel):
    media_asset_id: str
    detector_backend: str = Field("auto", pattern="^(auto|person|aerial|cctv|blob)$")
    clustering_method: str = Field("hac", pattern="^(hac|density)$")
    track_hold_seconds: float = Field(.6, ge=0, le=2)
    confidence_threshold: float = Field(0.3, ge=0.05, le=0.95)
    distance_threshold: float = Field(50.0, ge=5.0, le=500.0)
    linkage_method: str = Field("ward", pattern="^(ward|complete|average)$")
    sample_interval_frames: int = Field(5, ge=1, le=60)
    camera_mode: str = Field("auto", pattern="^(auto|static)$")
    chunk_duration_sec: float = Field(2., ge=0.5, le=10)
    motion_min_displacement_px: float = Field(1.5, ge=0, le=50)
    motion_smoothing: float = Field(0.5, gt=0, le=1)
    association_distance_px: float = Field(85., ge=5, le=500)
    crowd_increase: CrowdIncreaseConfig = Field(default_factory=CrowdIncreaseConfig)


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
    media_asset_id: Optional[str] = None
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
