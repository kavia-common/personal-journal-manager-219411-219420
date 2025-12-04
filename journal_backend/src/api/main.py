from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.db import init_db, get_session
from src.api.models import (
    JournalEntry,
    JournalEntryCreate,
    JournalEntryRead,
    JournalEntryUpdate,
)
from sqlmodel import select

openapi_tags = [
    {
        "name": "Health",
        "description": "Service health and diagnostics.",
    },
    {
        "name": "Journal Entries",
        "description": "CRUD operations for personal journal entries.",
    },
]

app = FastAPI(
    title="Personal Journal API",
    description="REST API for managing personal journal entries. Provides CRUD operations and OpenAPI docs.",
    version="0.1.0",
    openapi_tags=openapi_tags,
)

# Restrict CORS to Angular frontend on localhost:3000 as requested
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Initialize database on startup."""
    init_db()


# PUBLIC_INTERFACE
@app.get("/", tags=["Health"], summary="Health Check")
def health_check():
    """Health check endpoint to verify service is running."""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.get(
    "/api/journal-entries",
    response_model=List[JournalEntryRead],
    tags=["Journal Entries"],
    summary="List journal entries",
    description="Returns a list of all journal entries ordered by most recently updated.",
)
def list_journal_entries():
    """List all journal entries."""
    with get_session() as session:
        stmt = select(JournalEntry).order_by(JournalEntry.updated_at.desc())
        entries = session.exec(stmt).all()
        return [
            JournalEntryRead(
                id=e.id,
                title=e.title,
                content=e.content,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in entries
        ]


# PUBLIC_INTERFACE
@app.get(
    "/api/journal-entries/{entry_id}",
    response_model=JournalEntryRead,
    tags=["Journal Entries"],
    summary="Get a journal entry by ID",
    description="Fetch a single journal entry by its identifier.",
)
def get_journal_entry(
    entry_id: int = Path(..., description="The ID of the journal entry to fetch", ge=1)
):
    """Get a specific journal entry by id."""
    with get_session() as session:
        entry = session.get(JournalEntry, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        return JournalEntryRead(
            id=entry.id,
            title=entry.title,
            content=entry.content,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )


# PUBLIC_INTERFACE
@app.post(
    "/api/journal-entries",
    response_model=JournalEntryRead,
    status_code=201,
    tags=["Journal Entries"],
    summary="Create a new journal entry",
    description="Create a journal entry with title and content. Timestamps are set by the server.",
)
def create_journal_entry(payload: JournalEntryCreate):
    """Create a new journal entry."""
    now = datetime.utcnow()
    entry = JournalEntry(
        title=payload.title,
        content=payload.content,
        created_at=now,
        updated_at=now,
    )
    with get_session() as session:
        session.add(entry)
        session.flush()  # to populate autoincremented id
        return JournalEntryRead(
            id=entry.id,
            title=entry.title,
            content=entry.content,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )


# PUBLIC_INTERFACE
@app.put(
    "/api/journal-entries/{entry_id}",
    response_model=JournalEntryRead,
    tags=["Journal Entries"],
    summary="Update a journal entry",
    description="Update the title and/or content of an existing journal entry. The updated_at timestamp is refreshed.",
)
def update_journal_entry(
    payload: JournalEntryUpdate,
    entry_id: int = Path(..., description="The ID of the journal entry to update", ge=1),
):
    """Update existing journal entry."""
    with get_session() as session:
        entry = session.get(JournalEntry, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")

        updated = False
        if payload.title is not None and payload.title != entry.title:
            entry.title = payload.title
            updated = True
        if payload.content is not None and payload.content != entry.content:
            entry.content = payload.content
            updated = True

        if updated:
            entry.updated_at = datetime.utcnow()
            session.add(entry)
            session.flush()

        return JournalEntryRead(
            id=entry.id,
            title=entry.title,
            content=entry.content,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )


# PUBLIC_INTERFACE
@app.delete(
    "/api/journal-entries/{entry_id}",
    status_code=204,
    tags=["Journal Entries"],
    summary="Delete a journal entry",
    description="Delete a journal entry by ID.",
)
def delete_journal_entry(
    entry_id: int = Path(..., description="The ID of the journal entry to delete", ge=1)
):
    """Delete a journal entry by id."""
    with get_session() as session:
        entry = session.get(JournalEntry, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        session.delete(entry)
        session.flush()
    return JSONResponse(status_code=204, content=None)
