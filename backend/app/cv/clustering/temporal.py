"""Keep a spatial group's membership while its tracked members remain visible.

Clustering initializes groups and discovers new groups. Independent frame labels
do not replace existing identities. New members join a nearby observed member;
they do not merge two existing groups simply by briefly bridging them.
"""
import numpy as np
from app.cv.clustering.hac import ClusterGroup, ClusteringResult


class PersistentSpatialGroups:
    def __init__(self, clusterer, join_distance):
        self.clusterer=clusterer
        self.join_distance=join_distance
        self.members={}
        self.next_id=1
        self.pending_splits={}

    def cluster(self, observations, timestamp=0.):
        assigned={i:self.members[o['track_id']] for i,o in enumerate(observations) if o['track_id'] in self.members}
        anchors=list(assigned)
        for i,o in enumerate(observations):
            if i in assigned or not anchors:
                continue
            p=o['point']
            nearest=min(anchors,key=lambda j:np.hypot(p.x-observations[j]['point'].x,p.y-observations[j]['point'].y))
            q=observations[nearest]['point']
            if np.hypot(p.x-q.x,p.y-q.y)<=self.join_distance:
                assigned[i]=assigned[nearest]
        remaining=[i for i in range(len(observations)) if i not in assigned]
        discovered=self.clusterer.cluster([observations[i]['point'] for i in remaining])
        for group in discovered.clusters:
            gid=self.next_id;self.next_id+=1
            for index in group.member_indices:
                assigned[remaining[index]]=gid
        # Do not pin genuinely separating/oppositely moving crowds into one huge
        # polygon forever. Confirm separation over time before assigning child IDs.
        for gid in list(set(assigned.values())):
            indices=[i for i in assigned if assigned[i]==gid]
            parts=[]
            if len(indices)>=4:
                from sklearn.cluster import DBSCAN
                coords=np.array([[observations[i]['point'].x,observations[i]['point'].y] for i in indices])
                labels=DBSCAN(eps=self.join_distance*2,min_samples=1).fit_predict(coords)
                if len(set(labels))>1:
                    parts=[[indices[k] for k in np.where(labels==label)[0]] for label in set(labels)]
                else:
                    moving=[i for i in indices if observations[i].get('velocity') is not None
                            and np.linalg.norm(observations[i]['velocity'])>=5]
                    if len(moving)>=6:
                        units=np.array([observations[i]['velocity']/np.linalg.norm(observations[i]['velocity']) for i in moving])
                        _,axes=np.linalg.eigh(units.T@units)
                        axis=axes[:,-1]
                        positive=[i for i,u in zip(moving,units) if u@axis>=0]
                        negative=[i for i,u in zip(moving,units) if u@axis<0]
                        if min(len(positive),len(negative))>=max(3,len(moving)*.25):
                            coherence=[np.linalg.norm(np.mean([observations[i]['velocity']/np.linalg.norm(observations[i]['velocity']) for i in p],axis=0))
                                       for p in (positive,negative)]
                            if min(coherence)>.65:
                                rest=[i for i in indices if i not in moving]
                                parts=[positive+rest,negative]
            if len(parts)>1:
                start=self.pending_splits.setdefault(gid,timestamp)
                if timestamp-start>=.75:
                    parts.sort(key=len,reverse=True)
                    for part in parts[1:]:
                        child=self.next_id;self.next_id+=1
                        for i in part:assigned[i]=child
                    self.pending_splits.pop(gid,None)
            else:
                self.pending_splits.pop(gid,None)
        self.members={observations[i]['track_id']:gid for i,gid in assigned.items()}
        groups=[]
        for gid in sorted(set(assigned.values())):
            indices=[i for i in assigned if assigned[i]==gid]
            pts=[observations[i]['point'] for i in indices]
            coords=np.array([[p.x,p.y] for p in pts])
            groups.append(ClusterGroup(cluster_id=gid,member_indices=indices,member_points=pts,
                size=len(pts),centroid=coords.mean(0).tolist(),
                bounding_box=[*coords.min(0).tolist(),*coords.max(0).tolist()]))
        return ClusteringResult(clusters=groups,unclustered_points=[observations[i]['point'] for i in remaining if i not in assigned],
            distance_threshold=self.join_distance,linkage_method='persistent_membership')
