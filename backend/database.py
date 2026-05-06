"""
database.py
Connection to PostgreSQL + session factory. Same pattern as before -
nothing about the rework changes how the DB layer works, it just now
backs more tables (skills, preferences, patterns).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

import config

engine = create_engine(config.DATABASE_URL) if config.DATABASE_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import models  # noqa: F401
    if engine is None:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill in a real "
            "Postgres connection string before starting the server."
        )
    Base.metadata.create_all(bind=engine)
