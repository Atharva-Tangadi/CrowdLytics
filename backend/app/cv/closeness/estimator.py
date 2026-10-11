"""Closeness and spatial density estimation algorithms."""
from typing import List, Dict, Any, Optional
import numpy as np
from scipy.spatial import KDTree, ConvexHull
from scipy.spatial.distance import pdist
from pydantic import BaseModel, Field

from app.cv.clustering.hac import ClusterGroup


class GroupClosenessMetrics(BaseModel):
    """Closeness and compactness metrics for a specific cluster."""
    cluster_id: int
    size: int
    mean_nn_distance: float = Field(..., description="Mean 1-Nearest Neighbor distance in pixels")
    median_nn_distance: float = Field(..., description="Median 1-Nearest Neighbor distance in pixels")
    mean_pairwise_distance: float = Field(..., description="Mean pairwise Euclidean distance in pixels")
    dispersion: float = Field(..., description="Spatial variance / spread around cluster centroid")
    convex_hull_area: float = Field(..., description="Convex hull area in square pixels (0 if degenerate/collinear)")
    density_per_kpx: float = Field(..., description="Density (individuals per 1,000 square pixels)")
    is_degenerate: bool = Field(False, description="True if points are collinear or insufficient for 2D hull")


class AggregateClosenessSummary(BaseModel):
    """Overall closeness summary across all clusters."""
    total_grouped_individuals: int
    total_clusters: int
    global_mean_nn_distance: float
    global_median_nn_distance: float
    global_mean_density_per_kpx: float
    group_metrics: List[GroupClosenessMetrics]
    unit: str = "pixels"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClosenessEstimator:
    """Computes spatial closeness, dispersion, convex hull area, and density metrics."""

    def compute_group_metrics(self, cluster: ClusterGroup) -> GroupClosenessMetrics:
        pts = np.array([[p.x, p.y] for p in cluster.member_points], dtype=np.float64)
        n = len(pts)

        if n < 2:
            return GroupClosenessMetrics(
                cluster_id=cluster.cluster_id,
                size=n,
                mean_nn_distance=0.0,
                median_nn_distance=0.0,
                mean_pairwise_distance=0.0,
                dispersion=0.0,
                convex_hull_area=0.0,
                density_per_kpx=0.0,
                is_degenerate=True
            )

        # 1-Nearest Neighbor distances via KDTree
        tree = KDTree(pts)
        distances, _ = tree.query(pts, k=2)  # k=2 because k=1 is self-distance (0.0)
        nn_dists = distances[:, 1]
        mean_nn = float(np.mean(nn_dists))
        median_nn = float(np.median(nn_dists))

        # Mean pairwise distance
        pairwise_dists = pdist(pts)
        mean_pairwise = float(np.mean(pairwise_dists)) if len(pairwise_dists) > 0 else 0.0

        # Dispersion: mean distance from centroid
        centroid = np.array(cluster.centroid, dtype=np.float64)
        dispersion = float(np.mean(np.linalg.norm(pts - centroid, axis=1)))

        # Convex Hull Area
        hull_area = 0.0
        is_degenerate = False
        if n >= 3:
            try:
                hull = ConvexHull(pts)
                hull_area = float(hull.volume)  # In 2D, hull.volume represents area
            except Exception:
                # Collinear points or degenerate geometry
                is_degenerate = True
                hull_area = 0.0
        else:
            is_degenerate = True
            hull_area = 0.0

        # Estimated density per 1,000 square pixels
        if hull_area > 0:
            density_per_kpx = float((n / hull_area) * 1000.0)
        else:
            # Fallback using bounding box or dispersion radius
            bbox_w = cluster.bounding_box[2] - cluster.bounding_box[0]
            bbox_h = cluster.bounding_box[3] - cluster.bounding_box[1]
            approx_area = max(bbox_w * bbox_h, 1.0)
            density_per_kpx = float((n / approx_area) * 1000.0)

        return GroupClosenessMetrics(
            cluster_id=cluster.cluster_id,
            size=n,
            mean_nn_distance=mean_nn,
            median_nn_distance=median_nn,
            mean_pairwise_distance=mean_pairwise,
            dispersion=dispersion,
            convex_hull_area=hull_area,
            density_per_kpx=density_per_kpx,
            is_degenerate=is_degenerate
        )

    def compute_all(self, clusters: List[ClusterGroup]) -> AggregateClosenessSummary:
        if not clusters:
            return AggregateClosenessSummary(
                total_grouped_individuals=0,
                total_clusters=0,
                global_mean_nn_distance=0.0,
                global_median_nn_distance=0.0,
                global_mean_density_per_kpx=0.0,
                group_metrics=[]
            )

        metrics = [self.compute_group_metrics(c) for c in clusters]
        all_nn_means = [m.mean_nn_distance for m in metrics if m.size >= 2]
        all_nn_medians = [m.median_nn_distance for m in metrics if m.size >= 2]
        all_densities = [m.density_per_kpx for m in metrics]

        return AggregateClosenessSummary(
            total_grouped_individuals=sum(c.size for c in clusters),
            total_clusters=len(clusters),
            global_mean_nn_distance=float(np.mean(all_nn_means)) if all_nn_means else 0.0,
            global_median_nn_distance=float(np.median(all_nn_medians)) if all_nn_medians else 0.0,
            global_mean_density_per_kpx=float(np.mean(all_densities)) if all_densities else 0.0,
            group_metrics=metrics,
            unit="pixels"
        )
