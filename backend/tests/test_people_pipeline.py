from types import SimpleNamespace
import cv2
import numpy as np
import pytest
from app.cv.localization.detector import DetectionPoint
from app.cv.localization.person import PersonDetector
from app.cv.motion.people import PersonTracker, MembershipGroupTracker
from app.cv.clustering.density import DensityClusterer
from app.cv.clustering.temporal import PersistentSpatialGroups
from app.cv.analytics import summarize_frames


def point(x,y):
    return DetectionPoint(x=x,y=y,confidence=.9,bbox=[x-5,y-5,x+5,y+5])


def image(points):
    frame=np.zeros((200,300,3),np.uint8)
    for p in points:
        cv2.circle(frame,(round(p.x),round(p.y)),5,(255,255,255),-1)
    return frame


def test_optical_flow_maintains_members_boundary_and_direction_across_detection_dropout():
    people=PersonTracker(.6); groups=MembershipGroupTracker(); clustering=DensityClusterer(40)
    p0=[point(60,60),point(80,60),point(70,80)]
    first=people.update(p0,0,image=image(p0))
    c=clustering.cluster([o['point'] for o in first]); gid=groups.update(c.clusters,first,0)[0]['group_id']
    p1=[point(p.x+4,p.y) for p in p0]
    # The third person is still present in the image but is missed by the detector.
    second=people.update(p1[:2],.2,image(p0),image(p1))
    assert len(second)==3 and sum(o['observed'] for o in second)==2
    c=clustering.cluster([o['point'] for o in second]); g=groups.update(c.clusters,second,.2)[0]
    assert g['group_id']==gid
    assert g['direction_label']=='RIGHT'
    assert g['motion_speed']==pytest.approx(20,abs=2)
    assert g['observation_status']=='TRACKED'
    # An unavailable camera transform never produces borrowed/fabricated velocity.
    third=people.update(p1,.4,image(p1),image(p1),reliable=False)
    assert all(o['velocity'] is None for o in third)


def test_group_membership_survives_hac_label_and_size_changes():
    t=MembershipGroupTracker()
    obs=[dict(track_id=i,velocity=np.array([10.,0]),observed=True) for i in range(4)]
    a=SimpleNamespace(member_indices=[0,1,2]);b=SimpleNamespace(member_indices=[0,1,2,3])
    first=t.update([a],obs,0)[0]
    second=t.update([b],obs,.2)[0]
    assert first['group_id']==second['group_id']
    assert second['direction_label']=='RIGHT'


def test_mixed_opposing_motion_is_not_reported_as_a_precise_direction():
    t=MembershipGroupTracker()
    obs=[dict(track_id=i,velocity=np.array(v),observed=True) for i,v in enumerate([[10.,0],[-10.,0]])]
    result=t.update([SimpleNamespace(member_indices=[0,1])],obs,0)[0]
    assert result['motion_angle_deg'] is None
    assert result['direction_label']=='MIXED DIRECTIONS'


def test_person_model_tiled_coordinate_mapping_and_duplicate_suppression(tmp_path,monkeypatch):
    path=tmp_path/'model.onnx';path.write_bytes(b'test-model')
    outputs=[]
    # 500px image gets tiles at x=0 and x=116; both see the same person at x=200.
    for offset in (0,116):
        raw=np.zeros((1,5,8400),np.float32)
        raw[0,:,0]=[(200-offset)*640/384,100*640/384,20*640/384,30*640/384,.9]
        outputs.append(raw)
    net=SimpleNamespace(setInput=lambda _:None,forward=lambda:outputs.pop(0))
    monkeypatch.setattr(cv2.dnn,'readNetFromONNX',lambda _:net)
    detector=PersonDetector(path)
    result=detector.detect(np.zeros((300,500,3),np.uint8),.25)
    assert result.total_count==1
    assert result.points[0].x==pytest.approx(200)
    assert result.points[0].y==pytest.approx(100)


def test_model_missing_fails_instead_of_silent_blob_fallback(tmp_path):
    with pytest.raises(ValueError,match='model missing'):
        PersonDetector(tmp_path/'missing.onnx')


def test_high_threshold_returns_zero_with_diagnostics_not_a_silent_fallback(tmp_path,monkeypatch):
    path=tmp_path/'model.onnx';path.write_bytes(b'model')
    raw=np.zeros((1,5,8400),np.float32)
    raw[0,:,0]=[200,200,40,60,.8]
    net=SimpleNamespace(setInput=lambda _:None,forward=lambda:raw.copy())
    monkeypatch.setattr(cv2.dnn,'readNetFromONNX',lambda _:net)
    detector=PersonDetector(path)
    result=detector.detect(np.zeros((300,300,3),np.uint8),.9)
    assert result.total_count==0
    assert result.metadata['requested_threshold']==.9
    assert result.metadata['max_detection_score']==pytest.approx(.8)
    assert result.metadata['candidates_at_recommended_threshold']==1
    assert detector.detect(np.zeros((300,300,3),np.uint8),.25).total_count==1


def test_duration_weighted_occupancy_and_group_lifetime():
    frames=[dict(timestamp=0,valid_until=1,crowd_count=10,groups=[]),
            dict(timestamp=1,valid_until=4,crowd_count=20,groups=[])]
    result=summarize_frames(frames)
    assert result['mean_count']==pytest.approx(17.5)
    assert result['peak_count']==20


def test_persistent_group_does_not_vanish_or_relabel_when_frame_clustering_would_split():
    spatial=PersistentSpatialGroups(DensityClusterer(30),30)
    obs=[dict(track_id=i,point=point(x,60)) for i,x in enumerate([60,80,100])]
    first=spatial.cluster(obs).clusters[0]
    # Same tracked members spread apart and one detection drops; identity stays.
    obs=[dict(track_id=0,point=point(50,60)),dict(track_id=2,point=point(140,60))]
    second=spatial.cluster(obs).clusters
    assert len(second)==1 and second[0].cluster_id==first.cluster_id
    assert second[0].bounding_box==[50.,60.,140.,60.]
    # A remaining lone member keeps its marker/boundary; it is not a new group.
    assert spatial.cluster(obs[:1]).clusters[0].cluster_id==first.cluster_id
    assert not spatial.cluster([]).clusters


def test_sustained_opposing_motion_splits_group_without_framewise_id_churn():
    spatial=PersistentSpatialGroups(DensityClusterer(50),50)
    obs=[dict(track_id=i,point=point(40+i*10,80),velocity=np.array([15. if i<3 else -15.,0.])) for i in range(6)]
    first=spatial.cluster(obs,0).clusters
    assert len(first)==1
    assert len(spatial.cluster(obs,.4).clusters)==1
    split=spatial.cluster(obs,.8).clusters
    assert len(split)==2
    assert first[0].cluster_id in [g.cluster_id for g in split]
    assert [g.cluster_id for g in spatial.cluster(obs,1.).clusters]==[g.cluster_id for g in split]
