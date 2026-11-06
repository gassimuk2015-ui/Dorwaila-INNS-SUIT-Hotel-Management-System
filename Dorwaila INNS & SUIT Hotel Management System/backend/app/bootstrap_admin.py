"""Create the first Admin account. Run once with BOOTSTRAP_ADMIN_* environment variables."""

import os
import sys

from sqlalchemy import func, select

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models import User
from app.security import hash_password


def main() -> None:
    Base.metadata.create_all(bind=engine)
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    name = os.environ.get("BOOTSTRAP_ADMIN_NAME", "Hotel Administrator").strip()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email or len(password) < 12:
        sys.exit("Set BOOTSTRAP_ADMIN_EMAIL and a BOOTSTRAP_ADMIN_PASSWORD of at least 12 characters.")
    with SessionLocal() as db:
        if db.scalar(select(func.count(User.id))) != 0:
            sys.exit("Bootstrap refused: accounts already exist. Ask an Admin to create further accounts.")
        db.add(User(email=email, full_name=name, password_hash=hash_password(password), is_admin=True, is_active=True))
        db.commit()
    print(f"Initial Admin created for {email}.")


if __name__ == "__main__":
    main()

