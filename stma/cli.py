from __future__ import annotations

import argparse
import getpass
import os
import re

from sqlalchemy import select

from stma.database import create_database, initialize_database
from stma.models import LoginSession, User
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
    initialize_database(engine)
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


def reset_admin_password(username: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}", username):
        raise SystemExit("Username must be 3–80 letters, numbers, dots, underscores, or hyphens.")

    password = getpass.getpass("New Sysadmin password (minimum 12 characters): ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    url = os.getenv("DATABASE_URL", "sqlite:///./stma.db")
    engine, session_factory = create_database(url)
    initialize_database(engine)
    try:
        with session_factory.begin() as db:
            admin = db.scalar(
                select(User).where(User.username == username, User.role == "sysadmin")
            )
            if admin is None:
                raise SystemExit("No Sysadmin account with that username exists.")
            admin.password_hash = hash_password(password)
            for login in db.scalars(select(LoginSession).where(LoginSession.user_id == admin.id)):
                db.delete(login)
    finally:
        engine.dispose()
    print(f"Password reset for Sysadmin account '{username}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="STMA administrative commands")
    commands = parser.add_subparsers(dest="command", required=True)
    admin_parser = commands.add_parser("create-admin", help="Create the first Sysadmin account")
    admin_parser.add_argument("username")
    reset_parser = commands.add_parser(
        "reset-admin-password", help="Reset an existing Sysadmin account password"
    )
    reset_parser.add_argument("username")
    args = parser.parse_args()

    if args.command == "create-admin":
        create_admin(args.username)
    elif args.command == "reset-admin-password":
        reset_admin_password(args.username)


if __name__ == "__main__":
    main()
