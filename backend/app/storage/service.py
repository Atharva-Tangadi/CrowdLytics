"""Local private filesystem storage adapter."""
import os
import uuid
import math
from pathlib import Path
from typing import Tuple
import cv2

from app.core.config import settings


class StorageService:
    """Manages local file storage, path isolation, and media validation across data subdirectories."""

    def __init__(self, data_root: str = settings.DATA_ROOT):
        self.data_root = Path(data_root)
        self.uploads_dir = Path(settings.MEDIA_ROOT)
        self.processed_dir = Path(settings.PROCESSED_ROOT)
        self.results_dir = Path(settings.RESULTS_ROOT)
        self.temporary_dir = Path(settings.TEMPORARY_ROOT)

        # Ensure all data subdirectories exist
        for d in [self.data_root, self.uploads_dir, self.processed_dir, self.results_dir, self.temporary_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def save_upload(self, file_bytes: bytes, original_filename: str) -> Tuple[str, str, int, dict]:
        """
        Validates content and securely persists file under a random UUID key in data/uploads/.
        Returns: (storage_path, media_type, file_size, metadata)
        """
        ext = Path(original_filename).suffix.lower()
        allowed_images = {".jpg", ".jpeg", ".png"}
        if ext not in allowed_images | {".mp4", ".mov", ".avi"}:
            raise ValueError(f"Unsupported file extension: {ext}")
        limit = settings.MAX_IMAGE_SIZE_MB if ext in allowed_images else settings.MAX_VIDEO_SIZE_MB
        if len(file_bytes) > limit * 1024 * 1024:
            raise ValueError(f"Media exceeds {limit} MB limit.")
        file_uuid = str(uuid.uuid4())
        safe_filename = f"{file_uuid}{ext}"
        target_path = self.uploads_dir / safe_filename

        # Write to disk
        with open(target_path, "wb") as f:
            f.write(file_bytes)

        file_size = len(file_bytes)

        # Inspect format and dimensions
        metadata = {}
        if ext in [".jpg", ".jpeg", ".png"]:
            media_type = "IMAGE"
            img = cv2.imread(str(target_path))
            if img is None:
                target_path.unlink(missing_ok=True)
                raise ValueError("Corrupted or unsupported image file.")
            metadata["width"] = int(img.shape[1])
            metadata["height"] = int(img.shape[0])
        elif ext in [".mp4", ".mov", ".avi"]:
            media_type = "VIDEO"
            cap = cv2.VideoCapture(str(target_path))
            if not cap.isOpened():
                target_path.unlink(missing_ok=True)
                raise ValueError("Corrupted or unreadable video file.")
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = float(frame_count / fps) if fps > 0 else 0.0
            cap.release()
            if not math.isfinite(fps) or fps <= 0 or frame_count <= 0 or w <= 0 or h <= 0:
                target_path.unlink(missing_ok=True)
                raise ValueError("Invalid video dimensions, frame rate or duration.")
            if duration > settings.MAX_VIDEO_DURATION_SECONDS:
                target_path.unlink(missing_ok=True)
                raise ValueError("Video exceeds maximum duration.")
            metadata["width"] = w
            metadata["height"] = h
            metadata["fps"] = fps
            metadata["frame_count"] = frame_count
            metadata["duration_seconds"] = duration
        else:
            target_path.unlink(missing_ok=True)
            raise ValueError(f"Unsupported file extension: {ext}")

        return str(target_path), media_type, file_size, metadata

    def get_file_path(self, storage_path: str) -> Path:
        """Resolves path and verifies it resides within the private data root."""
        resolved = Path(storage_path).resolve()
        # Security check: must reside within data_root (or legacy storage directory)
        valid_roots = [self.data_root.resolve(), self.uploads_dir.resolve()]
        # Allow legacy storage if present
        legacy_storage = self.data_root.parent / "backend" / "storage"
        if legacy_storage.exists():
            valid_roots.append(legacy_storage.resolve())

        is_valid = any(
            resolved.is_relative_to(r) for r in valid_roots
        )
        if not is_valid:
            raise PermissionError("Access outside storage root is forbidden.")
        if not resolved.exists():
            raise FileNotFoundError("Storage file does not exist.")
        return resolved

    def delete_file(self, storage_path: str) -> None:
        """Deletes media file if it exists."""
        try:
            resolved = self.get_file_path(storage_path)
            resolved.unlink(missing_ok=True)
        except Exception:
            pass

    def cleanup_temporary(self) -> int:
        """Removes temporary processing artifacts and returns count of cleaned files."""
        count = 0
        try:
            for item in self.temporary_dir.iterdir():
                if item.is_file() and item.name != ".gitkeep":
                    item.unlink(missing_ok=True)
                    count += 1
        except Exception:
            pass
        return count


storage_service = StorageService()

