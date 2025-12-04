import os
from contextlib import contextmanager
from typing import Iterator

from sqlmodel import SQLModel, create_engine, Session

# Use a SQLite database file inside the backend container repository
DB_FILENAME = os.environ.get("JOURNAL_DB_FILENAME", "journal.db")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Store the DB at journal_backend/src/.. -> put at journal_backend/journal.db
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
DB_PATH = os.path.join(PROJECT_ROOT, DB_FILENAME)

DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    """
    Create database tables if missing.

    Note: SQLModel/SQLite create_all will not auto-migrate existing tables to add new columns.
    If running against an older DB missing created_at/updated_at/image_url, consider migrating
    or recreating the DB. Fresh environments will have correct schema.
    """
    SQLModel.metadata.create_all(engine)


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
