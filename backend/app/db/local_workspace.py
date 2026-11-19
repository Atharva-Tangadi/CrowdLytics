"""Compatibility owner for new sessions in the shared, login-free local workspace.

The legacy user table/foreign key is retained so existing databases need no
destructive migration. This row is bookkeeping, not an account that can log in.
"""
from sqlalchemy.exc import IntegrityError
from app.models.entities import User

LOCAL_OWNER_ID = "00000000-0000-0000-0000-000000000001"


def local_owner_id(db):
    if db.get(User, LOCAL_OWNER_ID) is None:
        try:
            with db.begin_nested():
                db.add(User(id=LOCAL_OWNER_ID, email="workspace@crowdlytics.local",
                            hashed_password="!login-disabled", role="local", is_active=False))
                db.flush()
        except IntegrityError:
            if db.get(User, LOCAL_OWNER_ID) is None:
                raise
    return LOCAL_OWNER_ID
