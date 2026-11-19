"""Finite, unique image-coordinate geometry shared by image and video outputs."""
import cv2
import numpy as np


def convex_hull(points):
    coords = np.asarray([[p.x, p.y] for p in points], dtype=np.float64).reshape(-1, 2)
    coords = np.unique(coords[np.isfinite(coords).all(axis=1)], axis=0)
    if len(coords) < 3 or np.linalg.matrix_rank(coords - coords[0]) < 2:
        return None
    try:
        hull = cv2.convexHull(coords.astype(np.float32)).reshape(-1, 2)
        return hull.astype(float).tolist() if cv2.contourArea(hull) > 0 else None
    except cv2.error:
        return None
