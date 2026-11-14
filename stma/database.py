from sqlalchemy import Index, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_database(url: str) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, factory


def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)

    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    with engine.begin() as connection:
        for column_name in ("first_name", "last_name", "school_id"):
            if column_name not in user_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} VARCHAR(80)"))
        if "student_id" in user_columns:
            connection.execute(
                text("UPDATE users SET school_id = student_id WHERE school_id IS NULL")
            )
    from stma.models import User

    Index("uq_users_school_id", User.school_id, unique=True).create(engine, checkfirst=True)
