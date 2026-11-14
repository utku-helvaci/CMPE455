from sqlalchemy import create_engine, inspect, text

from stma.main import create_app
from stma.models import Relationship, User


def test_existing_sqlite_users_table_gets_profile_columns(tmp_path):
    database_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id VARCHAR(36) PRIMARY KEY,
                    username VARCHAR(80) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    student_id VARCHAR(80),
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(text("CREATE UNIQUE INDEX uq_users_student_id ON users (student_id)"))
        connection.execute(
            text(
                """
                INSERT INTO users (id, username, password_hash, role, student_id, created_at)
                VALUES ('legacy-user-id', 'legacy-student', 'existing-hash', 'student',
                        'school-123', '2026-01-01 00:00:00')
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE relationships (
                    id VARCHAR(36) PRIMARY KEY,
                    student_id VARCHAR(36) NOT NULL,
                    evaluator_id VARCHAR(36) NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO relationships (id, student_id, evaluator_id, created_at)
                VALUES ('legacy-relationship', 'legacy-user-id', 'legacy-evaluator-id',
                        '2026-01-01 00:00:00')
                """
            )
        )
    engine.dispose()

    app = create_app(
        database_url=f"sqlite:///{database_path}",
        storage_dir=tmp_path / "storage",
    )
    columns = {column["name"] for column in inspect(app.state.engine).get_columns("users")}
    assert {"first_name", "last_name", "school_id"} <= columns
    relationship_columns = {
        column["name"] for column in inspect(app.state.engine).get_columns("relationships")
    }
    assert "active" in relationship_columns
    with app.state.session_factory() as db:
        legacy_user = db.get(User, "legacy-user-id")
        legacy_relationship = db.get(Relationship, "legacy-relationship")
        indexes = inspect(db.get_bind()).get_indexes("users")
    assert legacy_user is not None
    assert legacy_user.username == "legacy-student"
    assert legacy_user.first_name is None
    assert legacy_user.school_id == "school-123"
    assert legacy_relationship is not None
    assert legacy_relationship.active is True
    assert any(index["name"] == "uq_users_school_id" and index["unique"] for index in indexes)
