import json
import cv2
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import Base, engine


def workspace():
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    session = client.post('/api/v1/sessions',json={'title':'Enhancement demo'}).json()['id']
    return client, session


def test_image_geometry_media_identity_and_export():
    client, session = workspace()
    image = np.zeros((200,200,3),np.uint8)
    for xy in [(50,50),(65,50),(55,70)]:
        cv2.circle(image,xy,4,(255,255,255),-1)
    _, encoded = cv2.imencode('.png',image)
    media = client.post(f'/api/v1/sessions/{session}/media',files={'file':('test.png',encoded.tobytes(),'image/png')}).json()['id']
    job = client.post(f'/api/v1/sessions/{session}/analyze',json={'media_asset_id':media}).json()
    assert client.get(f'/api/v1/jobs/{job["id"]}').json()['status'] == 'COMPLETED'
    result = client.get(f'/api/v1/sessions/{session}/results').json()
    assert result['media_asset_id'] == media
    assert result['dominant_direction_deg'] is None
    assert all(g['motion_speed'] is None for g in result['groups'])
    assert len(json.loads(result['summary_data_json'])['group_annotations'][0]['convex_hull']) == 3
    export = client.get(f'/api/v1/sessions/{session}/results/export').json()
    assert export['media_asset_id'] == media
    assert export['analysis_details']['annotation_version'] == 3


def test_static_video_motion_crowd_event_and_incremental_chunks(tmp_path):
    client, session = workspace()
    path = tmp_path/'static.mp4'
    writer = cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(320,240))
    for i in range(45):
        frame = np.zeros((240,320,3),np.uint8)
        points = [(40+i,80),(55+i,80),(45+i,100)]
        if i >= 20:
            points += [(150+x*22,40+y*22) for x in range(4) for y in range(3)]
        for xy in points:
            cv2.circle(frame,xy,4,(255,255,255),-1)
        writer.write(frame)
    writer.release()
    media = client.post(f'/api/v1/sessions/{session}/media',files={'file':('static.mp4',path.read_bytes(),'video/mp4')}).json()['id']
    job = client.post(f'/api/v1/sessions/{session}/analyze',json={
        'media_asset_id':media,'camera_mode':'static','sample_interval_frames':1,
        'motion_min_displacement_px':.2,'motion_smoothing':1.,
        'crowd_increase':{'min_history_seconds':.5,'min_samples':3,'min_absolute':5,
                          'min_percent':50,'persistence_seconds':.5},
    }).json()
    status = client.get(f'/api/v1/jobs/{job["id"]}').json()
    assert status['status'] == 'COMPLETED', status
    chunks = client.get(f'/api/v1/jobs/{job["id"]}/chunks').json()
    frames = [frame for chunk in chunks for frame in json.loads(chunk['frame_data_json'])]
    assert len(frames) == 45
    assert all(a['timestamp'] < b['timestamp'] for a,b in zip(frames,frames[1:]))
    motions = [g for f in frames[2:18] for g in f['groups'] if g['motion_status'] == 'MOVING']
    assert motions and all(g['speed_unit'] == 'px/s' for g in motions)
    assert any(g['direction_label'] == 'RIGHT' and 5 < g['motion_speed'] < 15 for g in motions)
    assert any(f['crowd_event']['state'] == 'DETECTED' for f in frames)
    result = client.get(f'/api/v1/sessions/{session}/results').json()
    events = json.loads(result['summary_data_json'])['crowd_events']
    assert len([e for e in events if e['state'] == 'DETECTED']) == 1
    analytics = client.get(f'/api/v1/jobs/{job["id"]}/analytics').json()
    assert analytics['summary']['samples'] == 45
    assert len(analytics['frames']) == 45
    assert 'video_analytics' in json.loads(result['summary_data_json'])
    csv = client.get(f'/api/v1/jobs/{job["id"]}/analytics/export?format=csv')
    assert csv.status_code == 200 and 'timestamp,frame_index,crowd_count' in csv.text
    assert 'px/s' in csv.text
    assert client.get(f'/api/v1/jobs/{job["id"]}/analytics/export?format=json').json()['frames'] == analytics['frames']
    assert client.get('/api/v1/jobs/missing/analytics').status_code == 404

    assert client.get(f'/api/v1/jobs/{job["id"]}/chunks?after_index={chunks[-1]["chunk_index"]}').json() == []
    stranger, _ = workspace()
    assert stranger.get(f'/api/v1/jobs/{job["id"]}/chunks').status_code == 200


def test_running_cancellation_is_not_overwritten(tmp_path, monkeypatch):
    from app.cv.localization.detector import AerialBlobDensityDetector
    from app.db.session import SessionLocal
    from app.models.entities import AnalysisJob
    client, session = workspace()
    path = tmp_path/'cancel.mp4'
    writer = cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(100,100))
    for _ in range(10):
        writer.write(np.zeros((100,100,3),np.uint8))
    writer.release()
    media = client.post(f'/api/v1/sessions/{session}/media',files={'file':('cancel.mp4',path.read_bytes(),'video/mp4')}).json()['id']
    original = AerialBlobDensityDetector.detect
    calls = []
    def cancelling(self, *args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            with SessionLocal() as db:
                db.query(AnalysisJob).filter(AnalysisJob.session_id == session).update({'status':'CANCELLED'})
                db.commit()
        return original(self,*args,**kwargs)
    monkeypatch.setattr(AerialBlobDensityDetector,'detect',cancelling)
    job = client.post(f'/api/v1/sessions/{session}/analyze',json={
        'media_asset_id':media,'sample_interval_frames':1,'camera_mode':'static'}).json()
    assert client.get(f'/api/v1/jobs/{job["id"]}').json()['status'] == 'CANCELLED'
    assert client.get(f'/api/v1/sessions/{session}/results').json() is None
