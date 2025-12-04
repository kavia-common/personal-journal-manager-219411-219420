import os
from contextlib import contextmanager
from typing import Iterator, List, Tuple

from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text

# Use a SQLite database file inside the backend container repository
DB_FILENAME = os.environ.get("JOURNAL_DB_FILENAME", "journal.db")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Store the DB at journal_backend/src/.. -> put at journal_backend/journal.db
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
DB_PATH = os.path.join(PROJECT_ROOT, DB_FILENAME)

DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def _get_table_info(table: str) -> List[Tuple]:
    """
    Return PRAGMA table_info rows for the given table.
    Each row tuple: (cid, name, type, notnull, dflt_value, pk)
    """
    with engine.connect() as conn:
        res = conn.execute(text(f'PRAGMA table_info({table});'))
        return list(res.fetchall())


def _column_exists(table: str, column: str) -> bool:
    """
    Check if the specified column exists in a table.
    """
    for _cid, name, *_rest in _get_table_info(table):
        if name == column:
            return True
    return False


def _ensure_column(table: str, column: str, ddl: str) -> None:
    """
    Ensure a column exists on the SQLite table; if missing, add it using provided DDL.
    Example ddl: "ALTER TABLE journalentry ADD COLUMN image_url TEXT"
    """
    if not _column_exists(table, column):
        with engine.connect() as conn:
            conn.execute(text(ddl))
            conn.commit()


# PUBLIC_INTERFACE
def init_db() -> None:
    """
    Initialize the database and perform minimal, safe migrations.

    Behavior:
    - Creates tables from SQLModel metadata if they do not exist.
    - Performs additive migrations for legacy databases by adding missing columns:
      • image_url TEXT (nullable)
      • created_at DATETIME NOT NULL (added as nullable then backfilled in app code if needed)
      • updated_at DATETIME NOT NULL (added as nullable then backfilled in app code if needed)

    Note:
    - SQLite does not support altering constraints easily. We add columns without NOT NULL to
      avoid migration failures on existing rows; application code guards against NULLs in queries.
    - If more advanced migrations are required, consider a formal migration tool.
    """
    # Create tables if missing
    SQLModel.metadata.create_all(engine)

    # Minimal additive migrations for existing 'journalentry' table
    table = "journalentry"
    try:
        # Add image_url if missing
        _ensure_column(table, "image_url", f"ALTER TABLE {table} ADD COLUMN image_url TEXT")

        # created_at / updated_at columns should exist per current model. If missing in a legacy DB,
        # add them as nullable to avoid constraint issues; application code already guards NULLs.
        _ensure_column(table, "created_at", f"ALTER TABLE {table} ADD COLUMN created_at DATETIME")
        _ensure_column(table, "updated_at", f"ALTER TABLE {table} ADD COLUMN updated_at DATETIME")
    except Exception:
        # Do not fail startup due to migration issues; let endpoints surface detailed errors.
        # Raising would prevent the app from starting and hinder troubleshooting.
        pass


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed session for DB operations."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
