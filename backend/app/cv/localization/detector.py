"""Localization base interface and detector implementations."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np
import cv2
from pydantic import BaseModel, Field


class DetectionPoint(BaseModel):
    """Represents a localized individual / head center."""
    x: float = Field(..., description="X coordinate in pixels")
    y: float = Field(..., description="Y coordinate in pixels")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    bbox: Optional[List[float]] = Field(None, description="Optional bounding box [x1, y1, x2, y2]")


class DetectionResult(BaseModel):
    """Result of crowd localization."""
    points: List[DetectionPoint]
    total_count: int
    mean_confidence: float
    model_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseDetector(ABC):
    """Abstract interface for crowd / head localization detectors."""

    @abstractmethod
    def detect(self, image: np.ndarray, confidence_threshold: float = 0.3) -> DetectionResult:
        """Run detection on an image (BGR)."""
        pass


class DeterministicDetector(BaseDetector):
    """
    Deterministic detector for testing and synthetic validation.
    Allows injecting fixed coordinates or generating synthetic clusters.
    """

    def __init__(self, predefined_points: Optional[List[DetectionPoint]] = None):
        self.predefined_points = predefined_points or []

    def set_points(self, points: List[DetectionPoint]) -> None:
        self.predefined_points = points

    def detect(self, image: np.ndarray, confidence_threshold: float = 0.3) -> DetectionResult:
        valid_points = [p for p in self.predefined_points if p.confidence >= confidence_threshold]
        mean_conf = float(np.mean([p.confidence for p in valid_points])) if valid_points else 0.0
        return DetectionResult(
            points=valid_points,
            total_count=len(valid_points),
            mean_confidence=mean_conf,
            model_name="deterministic_fixture_v1",
            metadata={"threshold": confidence_threshold}
        )


class AerialBlobDensityDetector(BaseDetector):
    """
    Fast, lightweight spatial point localizer for high-altitude aerial imagery
    where people appear as small contrast blobs (e.g. 3x3 to 15x15 pixels).
    """

    def __init__(self, min_blob_radius: int = 2, max_blob_radius: int = 15):
        self.min_blob_radius = min_blob_radius
        self.max_blob_radius = max_blob_radius

    def detect(self, image: np.ndarray, confidence_threshold: float = 0.3) -> DetectionResult:
        if image is None or image.size == 0:
            return DetectionResult(
                points=[],
                total_count=0,
                mean_confidence=0.0,
                model_name="aerial_blob_density_v1"
            )

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Adaptive thresholding and morphological filtering to isolate head/torso blobs
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 15, 3
        )

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        points: List[DetectionPoint] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Filter by area corresponding to expected person/head footprint
            min_area = np.pi * (self.min_blob_radius ** 2)
            max_area = np.pi * (self.max_blob_radius ** 2)
            
            if min_area <= area <= max_area:
                M = cv2.moments(cnt)
                if M["m00"] > 0:
                    cX = float(M["m10"] / M["m00"])
                    cY = float(M["m01"] / M["m00"])
                    
                    # Compute circularity / solidity as a surrogate confidence metric
                    x, y, w, h = cv2.boundingRect(cnt)
                    aspect_ratio = float(w) / float(h) if h > 0 else 0
                    confidence = float(np.clip(1.0 - abs(1.0 - aspect_ratio), 0.3, 0.95))
                    
                    if confidence >= confidence_threshold:
                        points.append(
                            DetectionPoint(
                                x=cX,
                                y=cY,
                                confidence=confidence,
                                bbox=[float(x), float(y), float(x + w), float(y + h)]
                            )
                        )

        mean_conf = float(np.mean([p.confidence for p in points])) if points else 0.0
        return DetectionResult(
            points=points,
            total_count=len(points),
            mean_confidence=mean_conf,
            model_name="aerial_blob_density_v1",
            metadata={"contours_evaluated": len(contours)}
        )
