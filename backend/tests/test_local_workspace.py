from fastapi.testclient import TestClient
from app.main import app
from app.db.session import Base, engine, SessionLocal
from app.models.entities import User, AnalysisSession


def test_existing_accounts_and_sessions_preserved_and_visible():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        user = User(email='legacy-preserved@example.com',hashed_password='legacy-hash')
        db.add(user)
        db.flush()
        session = AnalysisSession(user_id=user.id,title='Pre-existing session')
        db.add(session)
        db.commit()
        session_id, user_id = session.id, user.id
    client = TestClient(app)
    assert session_id in [s['id'] for s in client.get('/api/v1/sessions').json()]
    assert client.get(f'/api/v1/sessions/{session_id}').status_code == 200
    for _ in range(2):
        assert client.post('/api/v1/sessions',json={'title':'No login'}).status_code == 201
    with SessionLocal() as db:
        assert db.get(User,user_id).hashed_password == 'legacy-hash'
        assert db.get(AnalysisSession,session_id).user_id == user_id
