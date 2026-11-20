import logging

from sqlalchemy import Index, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


school_id_index: Index | None = None


def create_database(url: str) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, factory


def _drop_plaintext_chat_table(engine: Engine) -> None:
    """Removes the chat table from before chat was encrypted.

    Messages used to be stored as readable text in a ``body`` column. They cannot be
    converted: signing a message needs the sender's private key, which the server never
    has. The old table is dropped and ``create_all`` recreates it in the encrypted format.
    """
    inspector = inspect(engine)
    if "chat_messages" not in inspector.get_table_names():
        return
    if "body" not in {column["name"] for column in inspector.get_columns("chat_messages")}:
        return
    with engine.begin() as connection:
        removed = connection.execute(text("SELECT COUNT(*) FROM chat_messages")).scalar_one()
        connection.execute(text("DROP TABLE chat_messages"))
    logger.warning(
        "Chat is now stored encrypted: removed the old plaintext chat table and its %d message(s).",
        removed,
    )


def initialize_database(engine: Engine) -> None:
    global school_id_index

    _drop_plaintext_chat_table(engine)
    Base.metadata.create_all(engine)

    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    relationship_columns = {
        column["name"] for column in inspect(engine).get_columns("relationships")
    }
    with engine.begin() as connection:
        for column_name in ("first_name", "last_name", "school_id"):
            if column_name not in user_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} VARCHAR(80)"))
        if "student_id" in user_columns:
            connection.execute(
                text("UPDATE users SET school_id = student_id WHERE school_id IS NULL")
            )
        if "active" not in relationship_columns:
            connection.execute(
                text("ALTER TABLE relationships ADD COLUMN active BOOLEAN NOT NULL DEFAULT TRUE")
            )
    if school_id_index is None:
        from stma.models import User

        school_id_index = Index("uq_users_school_id", User.school_id, unique=True)
    school_id_index.create(engine, checkfirst=True)
