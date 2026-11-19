import math
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
from app.cv.geometry import convex_hull
from app.cv.localization.detector import DetectionPoint
from app.cv.motion.groups import ClusterMotionTracker
from app.cv.motion.scene import register_scene, source_timestamp
from app.cv.formation.crowd_increase import CrowdIncreaseDetector
from app.schemas.api import CrowdIncreaseConfig


def cluster(x=100, y=100, size=3):
    return SimpleNamespace(centroid=[x, y], size=size, bounding_box=[x-10, y-10, x+10, y+10])


@pytest.mark.parametrize('coords,available', [
    ([(0, 0), (10, 0), (0, 10)], True),
    ([(0, 0), (10, 0), (0, 10), (10, 10), (0, 0)], True),
    ([(0, 0), (1, 1), (2, 2)], False),
    ([(0, 0)], False), ([(0, 0), (1, 1)], False),
    ([(float('nan'), 2), (0, 0), (10, 0), (0, 10)], True),
])
def test_hull(coords, available):
    result = convex_hull([DetectionPoint(x=x, y=y, confidence=.9) for x, y in coords])
    assert (result is not None) == available
    if result:
        assert len(result) >= 3 and np.isfinite(result).all()


@pytest.mark.parametrize('dx,dy,label,angle', [(10,0,'RIGHT',0),(-10,0,'LEFT',180),
    (0,-10,'UP',90),(0,10,'DOWN',270),(10,-10,'UP-RIGHT',45)])
def test_motion_directions_irregular_time(dx,dy,label,angle):
    tracker = ClusterMotionTracker(smoothing=1.)
    assert tracker.update([cluster()], .1)[0]['motion_speed'] is None
    result = tracker.update([cluster(100+dx,100+dy)], .6)[0]
    assert result['motion_speed'] == pytest.approx(math.hypot(dx,dy)/.5)
    assert result['motion_angle_deg'] == pytest.approx(angle)
    assert result['direction_label'] == label
    assert result['group_id'] == 1


def test_stationary_jitter_missing_and_uncertain():
    t = ClusterMotionTracker()
    t.update([cluster()], 0)
    assert t.update([cluster(100.2,100.1)], .2)[0]['motion_status'] == 'STATIONARY'
    assert t.update([cluster(102,100)], .4, reliable=False)[0]['motion_speed'] is None
    t.update([], .6)
    assert t.update([cluster()], .8)[0]['motion_status'] == 'COLLECTING_HISTORY'


def test_ambiguous_split_merge():
    t = ClusterMotionTracker()
    t.update([cluster()], 0)
    outputs = t.update([cluster(95), cluster(105)], .5)
    assert all(o['motion_speed'] is None for o in outputs)
    assert all(o['group_id'] != 1 for o in outputs)
    assert t.update([cluster(100)], 1)[0]['motion_speed'] is None


def test_affine_compensation_original_coordinates():
    t = ClusterMotionTracker(smoothing=1.)
    t.update([cluster()], 0)
    matrix = np.array([[0.,-1.,210.],[1.,0.,5.]])
    # Camera maps centroid to (110,105); crowd adds +10 x.
    result = t.update([cluster(120,105)], .5, matrix)[0]
    assert result['motion_speed'] == pytest.approx(20)


def detector(**kwargs):
    return CrowdIncreaseDetector(CrowdIncreaseConfig(min_history_seconds=2, min_samples=3,
        min_absolute=10, min_percent=50, persistence_seconds=1, cooldown_seconds=2, **kwargs))


def baseline(d, value=10):
    for ts in range(4):
        d.update(ts, value)


def test_sudden_persistence_cooldown_resolution():
    d = detector()
    baseline(d)
    assert d.update(4, 30)['state'] == 'CANDIDATE'
    assert d.update(5, 30)['state'] == 'DETECTED'
    for ts in range(6, 20):
        assert d.update(ts, 30)['state'] == 'COOLING_DOWN'
    assert len(d.events) == 1
    assert d.update(20, 10)['state'] == 'RESOLVED'


@pytest.mark.parametrize('counts', [[10]*20, list(range(10,30)), [10]*5+[30]+[10]*10, [10]*5+[15]*10])
def test_no_false_events(counts):
    d = detector()
    for ts, count in enumerate(counts):
        d.update(ts,count)
    assert not d.events


def test_zero_baseline_invalid_counts_and_history():
    d = detector()
    baseline(d, 0)
    d.update(4,20)
    result = d.update(5,20)
    assert result['state'] == 'DETECTED'
    assert result['percentage_increase'] is None
    for value in [None, -1, float('nan')]:
        assert d.update(6,value)['state'] == 'UNAVAILABLE'
    assert d.update(7,20)['state'] == 'WARMING_UP'


def test_static_featureless_and_camera_drift():
    a = np.zeros((200,300,3),np.uint8)
    assert register_scene(a,a,[],1.,'static')[1:3] == (True,True)
    rng = np.random.default_rng(42)
    textured = rng.integers(0,256,(200,300,3),dtype=np.uint8)
    moved = cv2.warpAffine(textured,np.float32([[1,0,5],[0,1,2]]),(300,200))
    matrix, valid, stable, _ = register_scene(textured,moved,[],.5,'auto')
    assert valid and not stable
    assert matrix[:,2] == pytest.approx([10,4],abs=.5)


def test_pts_and_fallback():
    cap = SimpleNamespace(get=lambda _: 750.)
    assert source_timestamp(cap,5,10,.4) == (.75,'presentation_timestamp')
    cap.get = lambda _: 0.
    assert source_timestamp(cap,10,10,.8) == (1.,'fps_fallback')
