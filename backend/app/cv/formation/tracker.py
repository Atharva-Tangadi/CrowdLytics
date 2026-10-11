"""Group formation dynamics and temporal transition classifier."""
from typing import List, Dict, Any, Optional
from enum import Enum
import numpy as np
from pydantic import BaseModel, Field

from app.cv.clustering.hac import ClusterGroup
from app.cv.closeness.estimator import GroupClosenessMetrics


class FormationType(str, Enum):
    CONVERGING = "converging"
    DISPERSING = "dispersing"
    EXPANDING = "expanding"
    CONTRACTING = "contracting"
    MERGING = "merging"
    SPLITTING = "splitting"
    STATIONARY = "stationary"
    UNCERTAIN = "uncertain"


class FormationChangeRecord(BaseModel):
    """Temporal classification for a cluster or cluster pair."""
    formation_type: FormationType
    cluster_id: Optional[int]
    confidence: float = Field(..., ge=0.0, le=1.0)
    description: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


class FormationTracker:
    """
    Classifies temporal group dynamics (merging, splitting, expansion,
    contraction, convergence, dispersion) between consecutive time windows.
    """

    def __init__(
        self,
        min_area_change_ratio: float = 0.20,
        min_centroid_movement_px: float = 5.0,
        min_confidence: float = 0.50
    ):
        self.min_area_change_ratio = min_area_change_ratio
        self.min_centroid_movement_px = min_centroid_movement_px
        self.min_confidence = min_confidence

    def analyze_temporal_transitions(
        self,
        prev_clusters: List[ClusterGroup],
        prev_metrics: List[GroupClosenessMetrics],
        curr_clusters: List[ClusterGroup],
        curr_metrics: List[GroupClosenessMetrics]
    ) -> List[FormationChangeRecord]:
        """Compares group topology across two time windows."""
        records: List[FormationChangeRecord] = []

        if not prev_clusters or not curr_clusters:
            return [
                FormationChangeRecord(
                    formation_type=FormationType.UNCERTAIN,
                    cluster_id=None,
                    confidence=0.0,
                    description="Insufficient cluster history to determine formation dynamics."
                )
            ]

        # 1. Macro-level Cluster Count Transitions (Split / Merge Detection)
        prev_count = len(prev_clusters)
        curr_count = len(curr_clusters)

        if curr_count < prev_count:
            # Possible merge: check if two previous centroids converged
            records.append(
                FormationChangeRecord(
                    formation_type=FormationType.MERGING,
                    cluster_id=None,
                    confidence=0.75,
                    description=f"Group count decreased from {prev_count} to {curr_count}, indicating crowd cluster consolidation/merging.",
                    evidence={"prev_clusters": prev_count, "curr_clusters": curr_count}
                )
            )
        elif curr_count > prev_count:
            # Possible split: check if a previous group partitioned
            records.append(
                FormationChangeRecord(
                    formation_type=FormationType.SPLITTING,
                    cluster_id=None,
                    confidence=0.75,
                    description=f"Group count increased from {prev_count} to {curr_count}, indicating crowd cluster subdivision/splitting.",
                    evidence={"prev_clusters": prev_count, "curr_clusters": curr_count}
                )
            )

        # 2. Individual Cluster Evolution (Centroid proximity matching)
        prev_metric_map = {m.cluster_id: m for m in prev_metrics}
        curr_metric_map = {m.cluster_id: m for m in curr_metrics}

        for prev_c in prev_clusters:
            # Find nearest corresponding cluster in current window
            best_curr = None
            min_dist = float("inf")
            for curr_c in curr_clusters:
                dist = np.hypot(
                    curr_c.centroid[0] - prev_c.centroid[0],
                    curr_c.centroid[1] - prev_c.centroid[1]
                )
                if dist < min_dist:
                    min_dist = dist
                    best_curr = curr_c

            if best_curr and min_dist < 100.0:  # Threshold for valid identity association
                p_metric = prev_metric_map.get(prev_c.cluster_id)
                c_metric = curr_metric_map.get(best_curr.cluster_id)

                if p_metric and c_metric:
                    # Area & Dispersion Comparison
                    p_area = max(p_metric.convex_hull_area, 1.0)
                    c_area = max(c_metric.convex_hull_area, 1.0)
                    area_delta_ratio = (c_area - p_area) / p_area

                    p_disp = p_metric.dispersion
                    c_disp = c_metric.dispersion
                    disp_delta_ratio = (c_disp - p_disp) / max(p_disp, 1.0)

                    # Expansion vs Contraction
                    if area_delta_ratio > self.min_area_change_ratio and disp_delta_ratio > 0.15:
                        records.append(
                            FormationChangeRecord(
                                formation_type=FormationType.EXPANDING,
                                cluster_id=best_curr.cluster_id,
                                confidence=0.80,
                                description=f"Cluster {best_curr.cluster_id} expanded: area increased by {area_delta_ratio*100:.1f}%.",
                                evidence={"area_ratio_change": area_delta_ratio, "dispersion_change": disp_delta_ratio}
                            )
                        )
                    elif area_delta_ratio < -self.min_area_change_ratio and disp_delta_ratio < -0.15:
                        records.append(
                            FormationChangeRecord(
                                formation_type=FormationType.CONTRACTING,
                                cluster_id=best_curr.cluster_id,
                                confidence=0.80,
                                description=f"Cluster {best_curr.cluster_id} contracted: area reduced by {abs(area_delta_ratio)*100:.1f}%.",
                                evidence={"area_ratio_change": area_delta_ratio, "dispersion_change": disp_delta_ratio}
                            )
                        )
                    # Convergence vs Dispersing (Mean nearest-neighbor distance)
                    elif c_metric.mean_nn_distance < p_metric.mean_nn_distance * 0.85:
                        records.append(
                            FormationChangeRecord(
                                formation_type=FormationType.CONVERGING,
                                cluster_id=best_curr.cluster_id,
                                confidence=0.75,
                                description=f"Cluster {best_curr.cluster_id} members converging closer together.",
                                evidence={"prev_mean_nn": p_metric.mean_nn_distance, "curr_mean_nn": c_metric.mean_nn_distance}
                            )
                        )
                    elif c_metric.mean_nn_distance > p_metric.mean_nn_distance * 1.15:
                        records.append(
                            FormationChangeRecord(
                                formation_type=FormationType.DISPERSING,
                                cluster_id=best_curr.cluster_id,
                                confidence=0.75,
                                description=f"Cluster {best_curr.cluster_id} members dispersing apart.",
                                evidence={"prev_mean_nn": p_metric.mean_nn_distance, "curr_mean_nn": c_metric.mean_nn_distance}
                            )
                        )
                    else:
                        records.append(
                            FormationChangeRecord(
                                formation_type=FormationType.STATIONARY,
                                cluster_id=best_curr.cluster_id,
                                confidence=0.85,
                                description=f"Cluster {best_curr.cluster_id} maintained stable spatial organization.",
                                evidence={"area_ratio_change": area_delta_ratio}
                            )
                        )

        if not records:
            records.append(
                FormationChangeRecord(
                    formation_type=FormationType.UNCERTAIN,
                    cluster_id=None,
                    confidence=0.3,
                    description="No definitive formation dynamic detected."
                )
            )

        return records
