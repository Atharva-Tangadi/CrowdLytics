"""Application settings loaded from environment variables."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "Aerial Crowd Intelligence"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    DEFAULT_DETECTOR: str = "person"
    PERSON_MODEL_PATH: str = str(BASE_DIR / "models" / "overhead_person.onnx")

    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/crowdlytics.db"

    # Storage (Local-First Layout)
    STORAGE_TYPE: str = "local"
    DATA_ROOT: str = str(BASE_DIR.parent / "data")
    MEDIA_ROOT: str = str(BASE_DIR.parent / "data" / "uploads")
    PROCESSED_ROOT: str = str(BASE_DIR.parent / "data" / "processed")
    RESULTS_ROOT: str = str(BASE_DIR.parent / "data" / "results")
    TEMPORARY_ROOT: str = str(BASE_DIR.parent / "data" / "temporary")

    # Limits
    MAX_IMAGE_SIZE_MB: int = 50
    MAX_VIDEO_SIZE_MB: int = 500
    MAX_VIDEO_DURATION_SECONDS: int = 300  # 5 minutes

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
