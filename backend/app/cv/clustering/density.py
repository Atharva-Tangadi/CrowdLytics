"""Spatial neighborhood grouping; HAC remains available for hierarchy comparisons."""
import numpy as np
from sklearn.cluster import DBSCAN
from app.cv.clustering.hac import ClusteringResult, ClusterGroup


class DensityClusterer:
    def __init__(self,distance_threshold=50.):
        self.distance_threshold=distance_threshold

    def cluster(self,points):
        groups=[];unclustered=[]
        if points:
            coords=np.array([[p.x,p.y] for p in points])
            labels=DBSCAN(eps=self.distance_threshold,min_samples=2).fit_predict(coords)
            for label in sorted(set(labels)):
                indices=np.where(labels==label)[0].tolist()
                if label<0:
                    unclustered.extend(points[i] for i in indices)
                    continue
                selected=coords[indices]
                groups.append(ClusterGroup(cluster_id=len(groups)+1,member_indices=indices,
                    member_points=[points[i] for i in indices],centroid=selected.mean(0).tolist(),size=len(indices),
                    bounding_box=[*selected.min(0).tolist(),*selected.max(0).tolist()]))
        return ClusteringResult(clusters=groups,unclustered_points=unclustered,
            distance_threshold=self.distance_threshold,linkage_method='density',cophenetic_correlation=None)
