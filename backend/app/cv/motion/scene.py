"""Lightweight scene registration with explicit uncertainty and source timestamps."""
import cv2
import numpy as np


def source_timestamp(cap, frame_index, fps, previous):
    pts = float(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000.
    if np.isfinite(pts) and pts >= 0 and (previous is None or pts > previous):
        return pts, "presentation_timestamp"
    fallback = frame_index / fps
    return max(fallback, (previous + 1 / fps) if previous is not None else 0.), "fps_fallback"


def register_scene(previous, current, previous_clusters, scale, mode):
    """Return original-coordinate affine transform, validity and scene stability.

    Static mode permits identity when featureless frames are similar; auto mode
    requires feature support. Even static mode checks for drift/cuts rather than
    blindly trusting the user's camera setting.
    """
    identity = np.eye(2, 3)
    if previous is None:
        return identity, False, False, "COLLECTING_HISTORY"
    if previous.shape != current.shape:
        return identity, False, False, "SCENE_CHANGED"
    prev = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    curr = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    mask = np.full(prev.shape, 255, np.uint8)
    for cluster in previous_clusters or []:
        x1, y1, x2, y2 = [int(v * scale) for v in cluster.bounding_box]
        cv2.rectangle(mask, (max(0, x1 - 15), max(0, y1 - 15)), (x2 + 15, y2 + 15), 0, -1)
    points = cv2.goodFeaturesToTrack(prev, 250, .01, 10, mask=mask)
    difference = float(np.mean(cv2.absdiff(prev, curr))) / 255
    # A fixed-camera declaration should not be rejected because moving people
    # dominate the feature matches. Large appearance changes still invalidate it.
    if mode == "static" and difference < .12:
        return identity, True, True, "STATIC_CONFIGURED"
    if points is None or len(points) < 8:
        reliable = mode == "static" and difference < .035
        return identity, reliable, reliable, "STATIC_ASSUMED" if reliable else "UNCERTAIN_CAMERA"
    tracked, status, _ = cv2.calcOpticalFlowPyrLK(prev, curr, points, None)
    if tracked is None or status is None:
        return identity, False, False, "UNCERTAIN_CAMERA"
    a, b = points[status.ravel() == 1], tracked[status.ravel() == 1]
    if len(a) < 8:
        return identity, False, False, "UNCERTAIN_CAMERA"
    matrix, inliers = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=2.)
    if matrix is None or inliers is None or np.mean(inliers) < .65:
        return identity, False, False, "SCENE_CHANGED"
    residual = np.linalg.norm(cv2.transform(a.reshape(-1, 1, 2), matrix).reshape(-1, 2) - b.reshape(-1, 2), axis=1)
    if np.median(residual[inliers.ravel() == 1]) > 1.5:
        return identity, False, False, "UNCERTAIN_CAMERA"
    zoom = float(np.hypot(matrix[0, 0], matrix[1, 0]))
    rotation = abs(float(np.arctan2(matrix[1, 0], matrix[0, 0])))
    matrix[:, 2] /= scale
    stable = abs(zoom - 1) < .01 and rotation < .01 and np.linalg.norm(matrix[:, 2]) < 2.
    # Big jumps/zoom invalidate the comparison; modest drift is compensated for motion.
    reliable = abs(zoom - 1) < .05 and rotation < .1 and np.linalg.norm(matrix[:, 2]) < 100
    return matrix, reliable, stable, "STATIC" if stable else "CAMERA_MOVING"
