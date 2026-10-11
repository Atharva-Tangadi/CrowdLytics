"""Motion analysis with camera motion compensation and collective direction estimation."""
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import cv2
from pydantic import BaseModel, Field


class MotionVector(BaseModel):
    """Local motion vector for a point or group."""
    x: float
    y: float
    dx: float = Field(..., description="Compensated horizontal velocity (px/frame)")
    dy: float = Field(..., description="Compensated vertical velocity (px/frame)")
    magnitude: float
    angle_degrees: float = Field(..., description="Angle [0, 360) in image coordinates (0 = right, 90 = down)")


class CollectiveMotionResult(BaseModel):
    """Aggregate motion characteristics for a frame or crowd group."""
    dominant_direction_deg: Optional[float] = Field(None, description="Circular mean direction [0, 360)")
    mean_speed: float = Field(..., description="Mean magnitude of compensated motion")
    directional_dispersion: float = Field(..., description="Circular variance [0, 1] where 0 is perfectly aligned")
    camera_motion_compensated: bool
    camera_shift: List[float] = Field(default_factory=lambda: [0.0, 0.0], description="[dx, dy] camera displacement")
    confidence: float = Field(..., ge=0.0, le=1.0)
    vectors: List[MotionVector] = Field(default_factory=list)


class VideoMotionAnalyzer:
    """
    Computes camera motion compensation and crowd movement vectors
    across sequential video frames.
    """

    def __init__(self, min_motion_threshold: float = 0.5):
        self.min_motion_threshold = min_motion_threshold

    def estimate_camera_motion(
        self, prev_gray: np.ndarray, curr_gray: np.ndarray
    ) -> Tuple[np.ndarray, bool]:
        """
        Estimates global background camera motion via GoodFeaturesToTrack and RANSAC affine transform.
        Returns: 2x3 affine transformation matrix and a boolean indicating success.
        """
        # Find feature points in background
        prev_pts = cv2.goodFeaturesToTrack(
            prev_gray, maxCorners=200, qualityLevel=0.01, minDistance=30, blockSize=3
        )
        if prev_pts is None or len(prev_pts) < 10:
            return np.eye(2, 3, dtype=np.float32), False

        # Track features to current frame
        curr_pts, status, err = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, prev_pts, None)
        valid_prev = prev_pts[status == 1]
        valid_curr = curr_pts[status == 1]

        if len(valid_prev) < 8:
            return np.eye(2, 3, dtype=np.float32), False

        # Estimate robust affine model via RANSAC
        matrix, inliers = cv2.estimateAffinePartial2D(valid_prev, valid_curr, method=cv2.RANSAC)
        if matrix is None:
            return np.eye(2, 3, dtype=np.float32), False

        return matrix, True

    def analyze_motion(
        self,
        prev_frame: np.ndarray,
        curr_frame: np.ndarray,
        crowd_points: Optional[List[Tuple[float, float]]] = None
    ) -> CollectiveMotionResult:
        """
        Analyzes motion between two consecutive frames.
        If crowd_points are provided, tracks sparse points; otherwise computes dense flow sampling.
        """
        if prev_frame is None or curr_frame is None:
            return CollectiveMotionResult(
                dominant_direction_deg=None,
                mean_speed=0.0,
                directional_dispersion=1.0,
                camera_motion_compensated=False,
                confidence=0.0
            )

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY) if len(prev_frame.shape) == 3 else prev_frame
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY) if len(curr_frame.shape) == 3 else curr_frame

        # 1. Camera Motion Compensation
        affine_matrix, cam_comp_ok = self.estimate_camera_motion(prev_gray, curr_gray)
        cam_dx = float(affine_matrix[0, 2])
        cam_dy = float(affine_matrix[1, 2])

        # 2. Crowd Flow Computation
        vectors: List[MotionVector] = []
        if crowd_points and len(crowd_points) > 0:
            pts_arr = np.array(crowd_points, dtype=np.float32).reshape(-1, 1, 2)
            tracked_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, pts_arr, None)

            for i, (orig, tracked, st) in enumerate(zip(crowd_points, tracked_pts, status)):
                if st[0] == 1:
                    raw_dx = tracked[0][0] - orig[0]
                    raw_dy = tracked[0][1] - orig[1]

                    # Subtract camera translation
                    comp_dx = raw_dx - cam_dx
                    comp_dy = raw_dy - cam_dy
                    mag = float(np.hypot(comp_dx, comp_dy))
                    angle = float(np.degrees(np.arctan2(comp_dy, comp_dx)) % 360.0)

                    if mag >= self.min_motion_threshold:
                        vectors.append(
                            MotionVector(
                                x=float(orig[0]),
                                y=float(orig[1]),
                                dx=float(comp_dx),
                                dy=float(comp_dy),
                                magnitude=mag,
                                angle_degrees=angle
                            )
                        )
        else:
            # Fallback to Farnebäck dense flow
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            step = 30
            h, w = flow.shape[:2]
            for y in range(0, h, step):
                for x in range(0, w, step):
                    raw_dx = flow[y, x, 0]
                    raw_dy = flow[y, x, 1]
                    comp_dx = raw_dx - cam_dx
                    comp_dy = raw_dy - cam_dy
                    mag = float(np.hypot(comp_dx, comp_dy))
                    angle = float(np.degrees(np.arctan2(comp_dy, comp_dx)) % 360.0)
                    if mag >= self.min_motion_threshold:
                        vectors.append(
                            MotionVector(
                                x=float(x),
                                y=float(y),
                                dx=float(comp_dx),
                                dy=float(comp_dy),
                                magnitude=mag,
                                angle_degrees=angle
                            )
                        )

        if not vectors:
            return CollectiveMotionResult(
                dominant_direction_deg=None,
                mean_speed=0.0,
                directional_dispersion=1.0,
                camera_motion_compensated=cam_comp_ok,
                camera_shift=[cam_dx, cam_dy],
                confidence=0.1 if cam_comp_ok else 0.0,
                vectors=[]
            )

        # 3. Directional Statistics (Circular Mean & Circular Variance)
        angles_rad = np.radians([v.angle_degrees for v in vectors])
        sin_sum = np.sum(np.sin(angles_rad))
        cos_sum = np.sum(np.cos(angles_rad))
        circ_mean_rad = np.arctan2(sin_sum, cos_sum)
        dominant_deg = float(np.degrees(circ_mean_rad) % 360.0)

        # Mean resultant vector length R in [0, 1]
        R = float(np.hypot(cos_sum, sin_sum) / len(vectors))
        dispersion = float(1.0 - R)  # Circular variance

        mean_speed = float(np.mean([v.magnitude for v in vectors]))
        confidence = float(np.clip(R * (min(len(vectors), 50) / 50.0), 0.1, 0.99))

        return CollectiveMotionResult(
            dominant_direction_deg=dominant_deg,
            mean_speed=mean_speed,
            directional_dispersion=dispersion,
            camera_motion_compensated=cam_comp_ok,
            camera_shift=[cam_dx, cam_dy],
            confidence=confidence,
            vectors=vectors
        )
