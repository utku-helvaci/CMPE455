from sqlalchemy import create_engine, inspect, text

from stma.main import create_app
from stma.models import ChatMessage


def test_plaintext_chat_table_is_replaced_by_the_encrypted_one(tmp_path):
    database_path = tmp_path / "legacy-chat.db"
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE chat_messages (
                    id VARCHAR(36) PRIMARY KEY,
                    relationship_id VARCHAR(36) NOT NULL,
                    sender_id VARCHAR(36) NOT NULL,
                    body VARCHAR(4000) NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO chat_messages (id, relationship_id, sender_id, body, created_at)
                VALUES ('old-message', 'old-relationship', 'old-sender', 'readable text',
                        '2026-01-01 00:00:00')
                """
            )
        )
    engine.dispose()

    app = create_app(database_url=f"sqlite:///{database_path}", storage_dir=tmp_path / "storage")

    columns = {column["name"] for column in inspect(app.state.engine).get_columns("chat_messages")}
    assert "body" not in columns
    assert {"ciphertext", "iv", "wrapped_des_key", "sender_wrapped_des_key"} <= columns
    with app.state.session_factory() as db:
        assert db.query(ChatMessage).count() == 0

    # Running the upgrade again on the new table changes nothing.
    create_app(database_url=f"sqlite:///{database_path}", storage_dir=tmp_path / "storage")
