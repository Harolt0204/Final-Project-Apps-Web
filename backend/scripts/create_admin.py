"""Create the first administrator account of a fresh (production) database.

The seed script is for development only; in production run this once:
    docker compose -f docker-compose.prod.yml exec app python -m scripts.create_admin \
        --username coordinacion
The password is read from the ADMIN_PASSWORD variable or asked interactively, so it never
appears in the shell history or the process list.
"""

import argparse
import getpass
import os
import re
import sys

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db import SessionLocal
from app.models import User, UserRole
from app.schemas.users import PASSWORD_MAX, PASSWORD_MIN

USERNAME_RE = re.compile(r"[a-z0-9]+([._-][a-z0-9]+)*")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--username", required=True, help="name.lastname, without @domain")
    username = parser.parse_args().username.strip().lower()
    if not USERNAME_RE.fullmatch(username):
        print("The user name must look like name.lastname (no @domain).", file=sys.stderr)
        return 1

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if not PASSWORD_MIN <= len(password.encode("utf-8")) <= PASSWORD_MAX:
        print(f"The password must have {PASSWORD_MIN}-{PASSWORD_MAX} characters.", file=sys.stderr)
        return 1

    db = SessionLocal()
    if db.scalars(select(User).where(func.lower(User.username) == username)).first():
        print("A user with this user name already exists.", file=sys.stderr)
        return 1
    db.add(User(username=username, password_hash=hash_password(password), role=UserRole.ADMIN))
    db.commit()
    print(f"Administrator {username} created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
