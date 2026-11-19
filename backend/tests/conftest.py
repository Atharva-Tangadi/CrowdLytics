"""Always isolate the legacy integration tests from user databases and uploads."""
import os
from pathlib import Path
import tempfile

_sandbox = tempfile.TemporaryDirectory(prefix="crowdlytics-tests-", ignore_cleanup_errors=True)
_root = Path(_sandbox.name)
os.environ["DATABASE_URL"] = "sqlite:///" + (_root / "test.db").as_posix()
os.environ["USE_CELERY"] = "false"
os.environ["DEFAULT_DETECTOR"] = "blob"  # Synthetic blobs are fixtures, not real people.
for key, folder in [("DATA_ROOT", "data"), ("MEDIA_ROOT", "data/uploads"),
                    ("PROCESSED_ROOT", "data/processed"), ("RESULTS_ROOT", "data/results"),
                    ("TEMPORARY_ROOT", "data/temporary")]:
    os.environ[key] = str(_root / folder)


def pytest_sessionfinish(session, exitstatus):
    import sys
    module = sys.modules.get("app.db.session")
    if module:
        module.engine.dispose()
