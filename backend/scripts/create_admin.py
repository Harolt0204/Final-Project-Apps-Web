"""Create the first administrator account of a fresh (production) database.

The seed script is for development only; in production run this once:
    docker compose -f docker-compose.prod.yml exec app python -m scripts.create_admin \
        --email coordinacion@yachaytech.edu.ec
The password is read from the ADMIN_PASSWORD variable or asked interactively, so it never
appears in the shell history or the process list.
"""

import argparse
import getpass
import os
import sys

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db import SessionLocal
from app.models import User, UserRole
from app.schemas.users import PASSWORD_MAX, PASSWORD_MIN


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    email = parser.parse_args().email.strip().lower()

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if not PASSWORD_MIN <= len(password.encode("utf-8")) <= PASSWORD_MAX:
        print(f"The password must have {PASSWORD_MIN}-{PASSWORD_MAX} characters.", file=sys.stderr)
        return 1

    db = SessionLocal()
    if db.scalars(select(User).where(func.lower(User.email) == email)).first():
        print("A user with this e-mail already exists.", file=sys.stderr)
        return 1
    db.add(User(email=email, password_hash=hash_password(password), role=UserRole.ADMIN))
    db.commit()
    print(f"Administrator {email} created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
