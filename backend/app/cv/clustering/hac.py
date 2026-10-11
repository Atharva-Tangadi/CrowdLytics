"""Hierarchical Agglomerative Clustering (HAC) implementation."""
from typing import List, Dict, Any, Optional
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster, cophenet
from scipy.spatial.distance import pdist
from pydantic import BaseModel, Field

from app.cv.localization.detector import DetectionPoint


class ClusterGroup(BaseModel):
    """Represents a grouped crowd cluster."""
    cluster_id: int
    member_indices: List[int]
    member_points: List[DetectionPoint]
    centroid: List[float] = Field(..., description="[x, y] coordinates of cluster centroid")
    size: int
    bounding_box: List[float] = Field(..., description="[min_x, min_y, max_x, max_y]")


class ClusteringResult(BaseModel):
    """Output of hierarchical agglomerative clustering."""
    clusters: List[ClusterGroup]
    unclustered_points: List[DetectionPoint] = Field(default_factory=list)
    cophenetic_correlation: Optional[float] = Field(None, description="Dendrogram distortion metric")
    distance_threshold: float
    linkage_method: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HierarchicalClusterer:
    """
    Performs agglomerative hierarchical clustering on spatial 2D coordinates.
    Supports Ward, Complete, and Average linkage criteria.
    """

    def __init__(
        self,
        distance_threshold: float = 50.0,
        linkage_method: str = "ward",
        min_cluster_size: int = 2
    ):
        """
        Args:
            distance_threshold: Maximum cophenetic distance for cluster cut-off (pixels or calibrated units).
            linkage_method: Linkage criterion ('ward', 'complete', 'average').
            min_cluster_size: Minimum number of members to form a valid group.
        """
        self.distance_threshold = distance_threshold
        self.linkage_method = linkage_method
        self.min_cluster_size = min_cluster_size

    def cluster(self, points: List[DetectionPoint]) -> ClusteringResult:
        if not points:
            return ClusteringResult(
                clusters=[],
                unclustered_points=[],
                cophenetic_correlation=None,
                distance_threshold=self.distance_threshold,
                linkage_method=self.linkage_method
            )

        if len(points) == 1:
            single = points[0]
            group = ClusterGroup(
                cluster_id=1,
                member_indices=[0],
                member_points=[single],
                centroid=[single.x, single.y],
                size=1,
                bounding_box=[single.x, single.y, single.x, single.y]
            )
            # If min_cluster_size > 1, classify as unclustered
            if self.min_cluster_size > 1:
                return ClusteringResult(
                    clusters=[],
                    unclustered_points=[single],
                    cophenetic_correlation=None,
                    distance_threshold=self.distance_threshold,
                    linkage_method=self.linkage_method
                )
            return ClusteringResult(
                clusters=[group],
                unclustered_points=[],
                cophenetic_correlation=None,
                distance_threshold=self.distance_threshold,
                linkage_method=self.linkage_method
            )

        coords = np.array([[p.x, p.y] for p in points], dtype=np.float64)

        # Compute hierarchical linkage matrix
        Z = linkage(coords, method=self.linkage_method)

        # Calculate cophenetic correlation coefficient to quantify dendrogram tree faithfulness
        cophenetic_val = None
        if len(coords) >= 3:
            try:
                coph_corr, _ = cophenet(Z, pdist(coords))
                cophenetic_val = float(coph_corr) if not np.isnan(coph_corr) else None
            except Exception:
                cophenetic_val = None

        # Form flat clusters using distance criterion
        labels = fcluster(Z, t=self.distance_threshold, criterion="distance")

        # Aggregate points by cluster label
        clusters_map: Dict[int, List[int]] = {}
        for idx, lbl in enumerate(labels):
            clusters_map.setdefault(int(lbl), []).append(idx)

        valid_clusters: List[ClusterGroup] = []
        unclustered: List[DetectionPoint] = []

        new_cluster_id = 1
        for orig_label, member_idxs in clusters_map.items():
            if len(member_idxs) >= self.min_cluster_size:
                pts = [points[i] for i in member_idxs]
                pts_coords = coords[member_idxs]
                centroid = [float(np.mean(pts_coords[:, 0])), float(np.mean(pts_coords[:, 1]))]
                bbox = [
                    float(np.min(pts_coords[:, 0])),
                    float(np.min(pts_coords[:, 1])),
                    float(np.max(pts_coords[:, 0])),
                    float(np.max(pts_coords[:, 1])),
                ]
                valid_clusters.append(
                    ClusterGroup(
                        cluster_id=new_cluster_id,
                        member_indices=member_idxs,
                        member_points=pts,
                        centroid=centroid,
                        size=len(pts),
                        bounding_box=bbox
                    )
                )
                new_cluster_id += 1
            else:
                for i in member_idxs:
                    unclustered.append(points[i])

        return ClusteringResult(
            clusters=valid_clusters,
            unclustered_points=unclustered,
            cophenetic_correlation=cophenetic_val,
            distance_threshold=self.distance_threshold,
            linkage_method=self.linkage_method,
            metadata={"total_points": len(points), "total_clusters": len(valid_clusters)}
        )
