"""Conservative group association and timestamp-normalized centroid motion.

Angles: atan2(-dy, dx), 0=right, 90=up. All distances are original-image pixels.
Ambiguous split/merge candidates get new IDs; they never borrow global motion.
"""
import math
import numpy as np
from scipy.optimize import linear_sum_assignment


def direction(angle):
    return ["RIGHT", "UP-RIGHT", "UP", "UP-LEFT", "LEFT", "DOWN-LEFT", "DOWN", "DOWN-RIGHT"][int((angle + 22.5) % 360 // 45)]


class ClusterMotionTracker:
    def __init__(self, max_distance=85., min_displacement=1.5, smoothing=0.5, max_gap=2.):
        self.max_distance = max_distance
        self.min_displacement = min_displacement
        self.smoothing = smoothing
        self.max_gap = max_gap
        self.tracks = {}
        self.next_id = 1

    def update(self, clusters, timestamp, transform=None, reliable=True):
        old = [(key, value) for key, value in self.tracks.items()
               if 0 < timestamp - value["timestamp"] <= self.max_gap]
        matrix = np.asarray(transform if transform is not None else np.eye(2, 3))
        projected = [matrix @ np.r_[v["centroid"], 1.] for _, v in old]
        cost = np.full((len(old), len(clusters)), 1e6)
        for i, (_, prev) in enumerate(old):
            for j, cluster in enumerate(clusters):
                distance = np.linalg.norm(np.asarray(cluster.centroid) - projected[i])
                ratio = cluster.size / max(prev["size"], 1)
                if distance <= self.max_distance and 0.67 <= ratio <= 1.5:
                    cost[i, j] = distance
        matches = {}
        if cost.size:
            for i, j in zip(*linear_sum_assignment(cost)):
                # A competing association within 10px is ambiguous, not an identity.
                rivals_row = np.delete(cost[i], j)
                rivals_col = np.delete(cost[:, j], i)
                if cost[i, j] < 1e6 and not np.any(rivals_row <= cost[i, j] + 10) and not np.any(rivals_col <= cost[i, j] + 10):
                    matches[j] = i
        outputs, tracks = [], {}
        for j, cluster in enumerate(clusters):
            status = "COLLECTING_HISTORY"
            speed = angle = None
            label = "Collecting motion history"
            velocity = None
            if j in matches:
                i = matches[j]
                gid, prev = old[i]
                dt = timestamp - prev["timestamp"]
                delta = np.asarray(cluster.centroid) - projected[i]
                if reliable:
                    if np.linalg.norm(delta) < self.min_displacement:
                        velocity = np.zeros(2)
                        speed, status, label = 0., "STATIONARY", "STATIONARY"
                    else:
                        velocity = delta / dt
                        if prev["velocity"] is not None:
                            velocity = self.smoothing * velocity + (1 - self.smoothing) * prev["velocity"]
                        speed = float(np.linalg.norm(velocity))
                        angle = float(math.degrees(math.atan2(-velocity[1], velocity[0])) % 360)
                        status, label = "MOVING", direction(angle)
                else:
                    status, label = "UNCERTAIN_CAMERA", "Camera motion uncertain"
            else:
                gid = self.next_id
                self.next_id += 1
                if old:
                    status, label = "UNCERTAIN_ASSOCIATION", "Association uncertain"
            tracks[gid] = dict(centroid=cluster.centroid, size=cluster.size,
                               timestamp=timestamp, velocity=velocity)
            outputs.append(dict(group_id=gid, motion_angle_deg=angle, motion_speed=speed,
                                speed_unit="px/s", motion_status=status, direction_label=label,
                                motion_confidence=1. if status in ("MOVING", "STATIONARY") else 0.))
        # Reappearance starts new history, avoiding fabricated motion over absent observations.
        self.tracks = tracks
        return outputs
