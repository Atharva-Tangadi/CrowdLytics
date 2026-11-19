import json
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import Base,engine,SessionLocal
from app.db.local_workspace import local_owner_id
from app.models.entities import AnalysisSession,MediaAsset,AnalysisJob,CrowdAnalysisResult


def test_empty_new_run_does_not_hide_or_overwrite_stored_positive_run():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        session=AnalysisSession(user_id=local_owner_id(db),title='History recovery')
        db.add(session);db.flush()
        media=MediaAsset(session_id=session.id,media_type='VIDEO',storage_path='unused',
            original_filename='test.mp4',file_size_bytes=1,mime_type='video/mp4')
        db.add(media);db.flush()
        ids=[]
        for threshold,count in [(.25,120),(.9,0)]:
            job=AnalysisJob(session_id=session.id,media_asset_id=media.id,status='COMPLETED',
                config_json=json.dumps({'confidence_threshold':threshold}),progress_pct=100)
            db.add(job);db.flush();ids.append(job.id)
            db.add(CrowdAnalysisResult(job_id=job.id,total_crowd_count=count,cluster_count=3 if count else 0,
                confidence_score=.7 if count else 0.,mean_closeness_px=10,mean_density_per_kpx=2,
                summary_data_json=json.dumps({'video_analytics':{'peak_count':count}})))
        session_id=session.id;db.commit()
    client=TestClient(app)
    history=client.get(f'/api/v1/sessions/{session_id}/jobs').json()
    assert len(history)==2
    assert {r['confidence_threshold'] for r in history}=={.25,.9}
    assert client.get(f'/api/v1/jobs/{ids[0]}/results').json()['total_crowd_count']==120
    assert client.get(f'/api/v1/jobs/{ids[1]}/results').json()['total_crowd_count']==0
    assert client.get('/api/v1/sessions/missing/jobs').status_code==404
    assert client.get('/api/v1/jobs/missing/results').status_code==404
