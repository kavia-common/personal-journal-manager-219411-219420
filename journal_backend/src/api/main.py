from datetime import datetime
import os
import secrets
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Path, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.db import init_db, get_session
from src.api.models import (
    JournalEntry,
    JournalEntryRead,
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

# CORS - keep Angular frontend allowed; allow localhost:3000 as specified
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static uploads directory setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # journal_backend/src/api -> src
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))  # journal_backend
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
# mount /static -> journal_backend/static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup() -> None:
    """Initialize database on startup."""
    init_db()


# Helpers
def _save_upload(file: UploadFile) -> str:
    """
    Save an uploaded image file to the uploads directory with a random name to avoid collisions.
    Returns the public URL path starting with /static/uploads/...
    """
    if file is None:
        return ""
    # Basic content-type guard (allow common image types)
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
    suffix = allowed.get(file.content_type, "")
    if not suffix:
        # If no recognized type, attempt to derive from filename extension; else default .bin
        _, ext = os.path.splitext(file.filename or "")
        suffix = ext if ext else ".bin"
    rand = secrets.token_hex(8)
    filename = f"{rand}{suffix}"
    dest_path = os.path.join(UPLOADS_DIR, filename)
    with open(dest_path, "wb") as out:
        out.write(file.file.read())
    return f"/static/uploads/{filename}"


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
                image_url=e.image_url,
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
            image_url=entry.image_url,
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
    description="Create a journal entry with title, content and optional image upload via multipart/form-data.",
)
async def create_journal_entry(
    title: str = Form(..., description="Title for the journal entry (1..200 chars)"),
    content: str = Form(..., description="Content/body for the entry (1..10000 chars)"),
    image: Optional[UploadFile] = File(None, description="Optional image file"),
):
    """Create a new journal entry. Accepts multipart/form-data with optional image file."""
    now = datetime.utcnow()
    image_url: Optional[str] = None
    if image is not None:
        image_url = _save_upload(image)

    entry = JournalEntry(
        title=title.strip(),
        content=content.strip(),
        image_url=image_url,
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
            image_url=entry.image_url,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )


# PUBLIC_INTERFACE
@app.put(
    "/api/journal-entries/{entry_id}",
    response_model=JournalEntryRead,
    tags=["Journal Entries"],
    summary="Update a journal entry",
    description="Update the title and/or content of an existing journal entry. Accepts multipart/form-data with optional image to replace or remove (pass image_remove=true).",
)
async def update_journal_entry(
    entry_id: int = Path(..., description="The ID of the journal entry to update", ge=1),
    title: Optional[str] = Form(None, description="Updated title (1..200 chars)"),
    content: Optional[str] = Form(None, description="Updated content (1..10000 chars)"),
    image: Optional[UploadFile] = File(None, description="Optional image file to replace existing"),
    image_remove: Optional[bool] = Form(False, description="Set true to remove existing image"),
):
    """Update existing journal entry with optional image replacement/removal."""
    with get_session() as session:
        entry = session.get(JournalEntry, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")

        updated = False

        if title is not None:
            t = title.strip()
            if not t:
                raise HTTPException(status_code=422, detail="Title must not be empty")
            if t != entry.title:
                entry.title = t
                updated = True

        if content is not None:
            c = content.strip()
            if not c:
                raise HTTPException(status_code=422, detail="Content must not be empty")
            if c != entry.content:
                entry.content = c
                updated = True

        # Handle image update/removal
        if image_remove:
            if entry.image_url:
                entry.image_url = None
                updated = True

        if image is not None:
            new_url = _save_upload(image)
            entry.image_url = new_url
            updated = True

        if updated:
            entry.updated_at = datetime.utcnow()
            session.add(entry)
            session.flush()

        return JournalEntryRead(
            id=entry.id,
            title=entry.title,
            content=entry.content,
            image_url=entry.image_url,
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
