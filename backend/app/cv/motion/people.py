"""Anonymous, within-video point tracks with measured optical-flow velocities."""
import math
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
from app.cv.localization.detector import DetectionPoint
from app.cv.motion.groups import direction


class PersonTracker:
    def __init__(self, hold_seconds=.6):
        self.tracks = {}
        self.next_id = 1
        self.hold_seconds = hold_seconds

    def update(self, points, timestamp, previous_image=None, image=None, scale=1., transform=None, reliable=True):
        transform = np.asarray(transform if transform is not None else np.eye(2,3))
        previous = list(self.tracks.items())
        flow = {}
        if previous and previous_image is not None and image is not None and previous_image.shape == image.shape:
            a = cv2.cvtColor(previous_image,cv2.COLOR_BGR2GRAY)
            b = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
            seeds = np.float32([[v['point'].x*scale,v['point'].y*scale] for _,v in previous]).reshape(-1,1,2)
            moved, valid, _ = cv2.calcOpticalFlowPyrLK(a,b,seeds,None,winSize=(21,21),maxLevel=3)
            if moved is not None:
                back, back_valid, _ = cv2.calcOpticalFlowPyrLK(b,a,moved,None,winSize=(21,21),maxLevel=3)
                if back is not None:
                    for i, (key, old) in enumerate(previous):
                        if valid[i,0] and back_valid[i,0] and np.linalg.norm(back[i]-seeds[i]) < 1.5:
                            position = moved[i,0]/scale
                            if 0 <= position[0] < image.shape[1]/scale and 0 <= position[1] < image.shape[0]/scale:
                                flow[key] = position
        predicted = [flow.get(k, transform @ np.r_[v['point'].x,v['point'].y,1.]) for k,v in previous]
        cost = np.full((len(previous),len(points)),1e6)
        for i, position in enumerate(predicted):
            for j,p in enumerate(points):
                dist = np.linalg.norm(position-[p.x,p.y])
                gate = 25.
                if p.bbox:
                    gate = min(45.,max(12.,np.hypot(p.bbox[2]-p.bbox[0],p.bbox[3]-p.bbox[1])*.8))
                if dist < gate:
                    cost[i,j] = dist
        matched = {}
        if cost.size:
            for i,j in zip(*linear_sum_assignment(cost)):
                if cost[i,j]<1e6:
                    matched[j] = i
        tracks, observations = {}, []
        used = set()
        for j,p in enumerate(points):
            old = None
            if j in matched:
                i = matched[j]; key,old=previous[i]; used.add(key)
            else:
                key=self.next_id;self.next_id+=1
            velocity = None
            if old and reliable and timestamp>old['timestamp']:
                # Flow at previous locations measures actual motion even when group membership changes.
                position = flow.get(key,np.array([p.x,p.y]))
                baseline = transform @ np.r_[old['point'].x,old['point'].y,1.]
                velocity = (position-baseline)/(timestamp-old['timestamp'])
                if old['velocity'] is not None:
                    velocity = .6*velocity+.4*old['velocity']
            tracks[key]=dict(point=p,timestamp=timestamp,last_observed=timestamp,velocity=velocity)
            observations.append(dict(track_id=key,point=p,velocity=velocity,observed=True))
        for key,old in previous:
            if (key not in used and key in flow and timestamp-old['last_observed'] <= self.hold_seconds
                    and not any(np.linalg.norm(flow[key]-[p.x,p.y])<6 for p in points)):
                position=flow[key]
                p=old['point'].model_copy(deep=True)
                dx,dy=position-[p.x,p.y];p.x,p.y=map(float,position)
                if p.bbox:
                    p.bbox=[p.bbox[0]+dx,p.bbox[1]+dy,p.bbox[2]+dx,p.bbox[3]+dy]
                tracks[key]=dict(old,point=p,timestamp=timestamp)
                observations.append(dict(track_id=key,point=p,velocity=old['velocity'] if reliable else None,observed=False))
        self.tracks=tracks
        return observations


class MembershipGroupTracker:
    """Persistent group IDs from member-track overlap, independent of HAC labels."""
    def __init__(self, use_cluster_ids=False):
        self.groups={}
        self.next_id=1
        self.use_cluster_ids=use_cluster_ids

    def update(self, clusters, observations, timestamp):
        members=[{observations[i]['track_id'] for i in c.member_indices} for c in clusters]
        previous=list(self.groups.items())
        cost=np.ones((len(previous),len(clusters)))
        for i,(_,old) in enumerate(previous):
            for j,ids in enumerate(members):
                cost[i,j]=1-len(old['members'] & ids)/max(len(old['members'] | ids),1)
        assigned={}
        if cost.size:
            for i,j in zip(*linear_sum_assignment(cost)):
                if cost[i,j] < .85:
                    assigned[j]=previous[i][0]
        output,new={},{}
        for j,c in enumerate(clusters):
            key=c.cluster_id if self.use_cluster_ids else assigned.get(j)
            if key is None:
                key=self.next_id;self.next_id+=1
            values=[observations[i]['velocity'] for i in c.member_indices if observations[i]['velocity'] is not None]
            angle=speed=None; label='Collecting motion history';status='COLLECTING_HISTORY';coherence=0.
            if values:
                vectors=np.asarray(values)
                lengths=np.linalg.norm(vectors,axis=1)
                moving=vectors[lengths>=2.]
                speed=float(np.median(lengths))
                if len(moving) == 0:
                    speed=0.;status=label='STATIONARY'
                else:
                    unit=moving/np.linalg.norm(moving,axis=1)[:,None]
                    coherence=float(np.linalg.norm(np.mean(unit,axis=0)))
                    if coherence>=.35:
                        mean=np.mean(unit,axis=0)
                        angle=float(math.degrees(math.atan2(-mean[1],mean[0]))%360)
                        label=direction(angle);status='MOVING'
                    else:
                        label='MIXED DIRECTIONS';status='MIXED'
            new[key]=dict(members=members[j],timestamp=timestamp)
            output[j]=dict(group_id=key,track_ids=sorted(members[j]),motion_angle_deg=angle,
                motion_speed=speed,speed_unit='px/s',motion_status=status,direction_label=label,
                motion_confidence=coherence,motion_support=len(values),
                observation_status='TRACKED' if any(not observations[i]['observed'] for i in c.member_indices) else 'DETECTED')
        self.groups=new
        return [output[j] for j in range(len(clusters))]
