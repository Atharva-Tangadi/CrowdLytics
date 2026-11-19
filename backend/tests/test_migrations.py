import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine, inspect


def test_fresh_alembic_database_includes_progressive_chunks(tmp_path):
    env = dict(os.environ, DATABASE_URL='sqlite:///' + (tmp_path/'migration.db').as_posix())
    completed = subprocess.run([sys.executable,'-m','alembic','upgrade','head'],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True,text=True,timeout=60)
    assert completed.returncode == 0, completed.stderr
    engine = create_engine(env['DATABASE_URL'])
    assert 'analysis_chunks' in inspect(engine).get_table_names()
    assert 'frame_data_json' in {c['name'] for c in inspect(engine).get_columns('analysis_chunks')}
    engine.dispose()
