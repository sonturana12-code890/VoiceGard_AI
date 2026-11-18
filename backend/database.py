"""
VOICEGUARD AI — Database Configuration
SQLite engine with SQLAlchemy ORM and connection pooling settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Resolve SQLite paths relative to the project root, not the process working directory.
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "voiceguard.db"

_database_url = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
)


def _resolve_database_url(database_url: str) -> str:
    # Render PostgreSQL compatibility (postgres:// -> postgresql://)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    parsed_url = make_url(database_url)
    if (
        parsed_url.get_backend_name() == "sqlite"
        and parsed_url.database
        and parsed_url.database != ":memory:"
        and not parsed_url.database.startswith("file:")
    ):
        database_path = Path(parsed_url.database)
        if not database_path.is_absolute():
            database_path = (PROJECT_ROOT / database_path).resolve()
            parsed_url = parsed_url.set(database=str(database_path))
    return parsed_url.render_as_string(hide_password=False)


DATABASE_URL = _resolve_database_url(_database_url)

# SQLite specific connect args
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=os.environ.get("DEBUG", "false").lower() == "true",
)

# Enable Foreign Keys and WAL Mode on SQLite connections
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a SQLAlchemy session per request
    and ensures proper closing on completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables according to defined models and apply lightweight SQLite migrations."""
    import backend.models  # Ensure models are loaded # noqa: F401
    Base.metadata.create_all(bind=engine)

    # SQLite migration: Ensure new columns exist on existing tables
    if DATABASE_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                cursor = conn.connection.cursor()
                cursor.execute("PRAGMA table_info(speaker_registrations)")
                existing_cols = {row[1] for row in cursor.fetchall()}

                columns_to_add = [
                    ("speaker_id", "VARCHAR(64)"),
                    ("voiceprint_embedding", "TEXT"),
                    ("voiceprint_status", "VARCHAR(32) DEFAULT 'ACTIVE'"),
                    ("audio_duration_seconds", "FLOAT"),
                    ("last_verified_at", "DATETIME"),
                    ("verification_count", "INTEGER DEFAULT 0"),
                    ("updated_at", "DATETIME"),
                ]
                for col_name, col_type in columns_to_add:
                    if col_name not in existing_cols:
                        try:
                            cursor.execute(f"ALTER TABLE speaker_registrations ADD COLUMN {col_name} {col_type}")
                        except Exception:
                            pass
                conn.connection.commit()
                cursor.close()
        except Exception:
            pass

