"""
database.py
Connection to PostgreSQL + session factory. Same pattern as before -
nothing about the rework changes how the DB layer works, it just now
backs more tables (skills, preferences, patterns).
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

import config

engine = create_engine(config.DATABASE_URL) if config.DATABASE_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None

Base = declarative_base()


def _upgrade_task_schema() -> None:
    """Add persisted-chat columns to databases created by earlier releases."""
    existing_columns = {
        column["name"] for column in inspect(engine).get_columns("tasks")
    }
    missing_columns = {
        "transcript": "TEXT",
        "raw_messages": "TEXT",
        "workbook_name": "VARCHAR",
        "is_read": "BOOLEAN NOT NULL DEFAULT FALSE",
    }

    with engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_type}")
                )


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
    _upgrade_task_schema()
