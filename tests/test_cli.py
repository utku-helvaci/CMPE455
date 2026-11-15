from datetime import UTC, datetime, timedelta

import pytest

from stma.cli import reset_admin_password
from stma.database import create_database, initialize_database
from stma.models import LoginSession, User
from stma.security import hash_password, verify_password


def test_reset_admin_password_updates_hash_and_revokes_sessions(tmp_path, monkeypatch):
    database_path = tmp_path / "admin-reset.db"
    engine, session_factory = create_database(f"sqlite:///{database_path}")
    initialize_database(engine)
    with session_factory.begin() as db:
        admin = User(
            username="sysadmin",
            password_hash=hash_password("old admin password"),
            role="sysadmin",
        )
        db.add(admin)
        db.flush()
        db.add(
            LoginSession(
                user_id=admin.id,
                token_hash="a" * 64,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
    engine.dispose()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    prompts = iter(("new admin password", "new admin password"))
    monkeypatch.setattr("stma.cli.getpass.getpass", lambda _: next(prompts))

    reset_admin_password("sysadmin")

    engine, session_factory = create_database(f"sqlite:///{database_path}")
    try:
        with session_factory() as db:
            admin = db.query(User).filter_by(username="sysadmin").one()
            assert verify_password(admin.password_hash, "new admin password")
            assert not verify_password(admin.password_hash, "old admin password")
            assert db.query(LoginSession).filter_by(user_id=admin.id).count() == 0
    finally:
        engine.dispose()


def test_reset_admin_password_rejects_mismatched_confirmation(tmp_path, monkeypatch):
    database_path = tmp_path / "admin-reset-mismatch.db"
    engine, _ = create_database(f"sqlite:///{database_path}")
    initialize_database(engine)
    engine.dispose()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    prompts = iter(("new admin password", "different admin password"))
    monkeypatch.setattr("stma.cli.getpass.getpass", lambda _: next(prompts))

    with pytest.raises(SystemExit, match="Passwords do not match"):
        reset_admin_password("sysadmin")
