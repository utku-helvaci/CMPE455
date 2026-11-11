from __future__ import annotations

import argparse
import getpass
import os
import re

from sqlalchemy import select

from stma.database import Base, create_database
from stma.models import User
from stma.security import hash_password


def create_admin(username: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}", username):
        raise SystemExit("Username must be 3–80 letters, numbers, dots, underscores, or hyphens.")

    password = getpass.getpass("Sysadmin password (minimum 12 characters): ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    url = os.getenv("DATABASE_URL", "sqlite:///./stma.db")
    engine, session_factory = create_database(url)
    Base.metadata.create_all(engine)
    try:
        with session_factory.begin() as db:
            if db.scalar(select(User.id).where(User.username == username)) is not None:
                raise SystemExit("That username already exists.")
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    role="sysadmin",
                )
            )
    finally:
        engine.dispose()
    print(f"Sysadmin account '{username}' created.")


def main() -> None:
    parser = argparse.ArgumentParser(description="STMA administrative commands")
    commands = parser.add_subparsers(dest="command", required=True)
    admin_parser = commands.add_parser("create-admin", help="Create the first Sysadmin account")
    admin_parser.add_argument("username")
    args = parser.parse_args()

    if args.command == "create-admin":
        create_admin(args.username)


if __name__ == "__main__":
    main()
