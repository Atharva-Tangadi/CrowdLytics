"""Group-level visualization generators for overlaying crowd analysis on media frames."""
from typing import List, Tuple, Optional
import numpy as np
import cv2

from app.cv.clustering.hac import ClusterGroup
from app.cv.motion.analyzer import MotionVector


# High-contrast color palette for visual cluster differentiation
CLUSTER_COLORS = [
    (239, 68, 68),    # Red
    (59, 130, 246),   # Blue
    (16, 185, 129),   # Emerald
    (245, 158, 11),   # Amber
    (168, 85, 247),   # Purple
    (236, 72, 153),   # Pink
    (6, 182, 212),    # Cyan
    (234, 179, 8),    # Yellow
]


class GroupVisualizer:
    """Renders non-invasive group-level visual overlays on images/frames."""

    def render_overlays(
        self,
        image: np.ndarray,
        clusters: List[ClusterGroup],
        motion_vectors: Optional[List[MotionVector]] = None,
        draw_convex_hull: bool = True,
        draw_centroids: bool = True,
        draw_bounding_box: bool = True
    ) -> np.ndarray:
        """Draws group hulls, centroids, bounding boxes, and collective motion vectors."""
        if image is None:
            raise ValueError("Invalid image for overlay.")

        annotated = image.copy()
        h, w = annotated.shape[:2]

        # Draw Clusters
        for idx, cluster in enumerate(clusters):
            color = CLUSTER_COLORS[idx % len(CLUSTER_COLORS)]
            pts = np.array([[int(round(p.x)), int(round(p.y))] for p in cluster.member_points])

            # 1. Convex Hull Polygon
            if draw_convex_hull and len(pts) >= 3:
                try:
                    hull = cv2.convexHull(pts)
                    # Semi-transparent polygon overlay
                    overlay = annotated.copy()
                    cv2.fillPoly(overlay, [hull], color)
                    cv2.addWeighted(overlay, 0.25, annotated, 0.75, 0, annotated)
                    cv2.polylines(annotated, [hull], isClosed=True, color=color, thickness=2)
                except Exception:
                    pass

            # 2. Bounding Box
            if draw_bounding_box:
                bx1, by1, bx2, by2 = [int(round(v)) for v in cluster.bounding_box]
                cv2.rectangle(annotated, (bx1, by1), (bx2, by2), color, 1, cv2.LINE_AA)
                label = f"G{cluster.cluster_id} (n={cluster.size})"
                cv2.putText(
                    annotated, label, (bx1, max(by1 - 6, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA
                )

            # 3. Centroid Marker
            if draw_centroids:
                cx, cy = int(round(cluster.centroid[0])), int(round(cluster.centroid[1]))
                cv2.drawMarker(
                    annotated, (cx, cy), color,
                    markerType=cv2.MARKER_CROSS, markerSize=12, thickness=2
                )

        # Draw Motion Vectors
        if motion_vectors:
            for vec in motion_vectors:
                start_pt = (int(round(vec.x)), int(round(vec.y)))
                end_pt = (
                    int(round(vec.x + vec.dx * 2.0)),
                    int(round(vec.y + vec.dy * 2.0))
                )
                cv2.arrowedLine(
                    annotated, start_pt, end_pt,
                    (0, 255, 255), 2, tipLength=0.3
                )

        return annotated
