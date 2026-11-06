"""Create tables for a local development database. Use versioned migrations in production."""

from app.database import Base, engine
from app import models  # noqa: F401

Base.metadata.create_all(bind=engine)
print("Development database tables created.")

