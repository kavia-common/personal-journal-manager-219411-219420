from datetime import datetime, date
import os
import secrets
from typing import List, Optional, Set, Dict, Any

from fastapi import FastAPI, HTTPException, Path, UploadFile, File, Form, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from src.api.db import init_db, get_session
from src.api.models import (
    JournalEntry,
    JournalEntryRead,
    JournalEntryCreate,
    JournalEntryUpdate,
)
from sqlmodel import select

# Define simple Pydantic models for internal endpoints to ensure OpenAPI serialization
from pydantic import BaseModel, Field


# PUBLIC_INTERFACE
class VerifyResult(BaseModel):
    """Result model for verification endpoints."""
    status_code: Optional[int] = Field(None, description="HTTP status code from the internal request")
    create_status: Optional[int] = Field(None, description="HTTP status code from create operation")
    update_status: Optional[int] = Field(None, description="HTTP status code from update operation")
    json: Optional[Dict[str, Any]] = Field(None, description="JSON payload returned")
    updated: Optional[Dict[str, Any]] = Field(None, description="Updated entry JSON payload")

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
    version="0.1.1",
    openapi_tags=openapi_tags,
)

# CORS - allow Angular frontend based on environment with safe defaults.
# Prefer ALLOWED_ORIGINS (comma-separated) else fall back to NG_APP_FRONTEND_URL, else permissive "*"
raw_origins = os.environ.get("ALLOWED_ORIGINS")
if raw_origins:
    allow_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
else:
    frontend_origin = os.environ.get("NG_APP_FRONTEND_URL")
    allow_origins = [frontend_origin] if frontend_origin else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
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


# PUBLIC_INTERFACE
@app.post(
    "/api/journal-entries/_verify-post",
    response_model=JournalEntryRead,
    tags=["Journal Entries"],
    summary="Internal verification: sample POST",
    description="Creates a sample entry using application/json to verify 201 response path without image. Not for production use.",
)
def verify_post_sample():
    """Create a minimal sample entry to verify JSON create path returns 201."""
    now = datetime.utcnow()
    entry = JournalEntry(
        title="Sample Verification",
        content="This is a verification entry.",
        created_at=now,
        updated_at=now,
    )
    with get_session() as session:
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
@app.post(
    "/api/journal-entries/_verify-create-json",
    response_model=VerifyResult,
    tags=["Journal Entries"],
    summary="Internal: verify JSON create path",
    description="Sends an application/json request to POST /api/journal-entries and returns the result.",
)
async def verify_create_json():
    """Internal helper to verify application/json create path."""
    try:
        from fastapi.testclient import TestClient  # local usage without network
        client = TestClient(app)
        resp = client.post("/api/journal-entries", json={"title": "JSON Title", "content": ""})
        return {"status_code": resp.status_code, "json": resp.json()}
    except Exception as exc:
        raise _structured_500("Verification failed (JSON create)", {"exception": str(exc)})

# PUBLIC_INTERFACE
@app.post(
    "/api/journal-entries/_verify-update-json",
    response_model=VerifyResult,
    tags=["Journal Entries"],
    summary="Internal: verify JSON update path",
    description="Creates an entry then updates it via application/json to verify 200 response.",
)
async def verify_update_json():
    """Simulate JSON PUT update."""
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app)
        create = client.post("/api/journal-entries", json={"title": "To Update", "content": ""})
        eid = create.json()["id"]
        upd = client.put(f"/api/journal-entries/{eid}", json={"title": "Updated Title"})
        return {"create_status": create.status_code, "update_status": upd.status_code, "updated": upd.json()}
    except Exception as exc:
        raise _structured_500("Verification failed (JSON update)", {"exception": str(exc)})

# PUBLIC_INTERFACE
@app.post(
    "/api/journal-entries/_verify-update-multipart",
    response_model=VerifyResult,
    tags=["Journal Entries"],
    summary="Internal: verify multipart update path",
    description="Creates an entry then updates it via multipart/form-data to verify 200 response.",
)
async def verify_update_multipart():
    """Simulate multipart PUT update without a file."""
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app)
        create = client.post("/api/journal-entries", json={"title": "To Update MP", "content": ""})
        eid = create.json()["id"]
        upd = client.put(f"/api/journal-entries/{eid}", data={"title": "MP Updated", "content": ""}, files={})
        return {"create_status": create.status_code, "update_status": upd.status_code, "updated": upd.json()}
    except Exception as exc:
        raise _structured_500("Verification failed (multipart update)", {"exception": str(exc)})


# PUBLIC_INTERFACE
@app.post(
    "/api/journal-entries/_verify-create-multipart",
    response_model=VerifyResult,
    tags=["Journal Entries"],
    summary="Internal: verify multipart create path",
    description="Sends a multipart/form-data request to POST /api/journal-entries (no file) and returns the result.",
)
async def verify_create_multipart():
    """Internal helper to verify multipart/form-data create path."""
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.post(
            "/api/journal-entries",
            files={},  # no image
            data={"title": "MP Title", "content": ""},
        )
        return {"status_code": resp.status_code, "json": resp.json()}
    except Exception as exc:
        raise _structured_500("Verification failed (multipart create)", {"exception": str(exc)})

# PUBLIC_INTERFACE
# PUBLIC_INTERFACE
class InspectResult(BaseModel):
    """Response model for request inspection."""
    content_type: str = Field(..., description="Content-Type header of the request")
    has_json_payload: bool = Field(..., description="Whether a JSON payload was parsed")
    json_payload: Optional[Dict[str, Any]] = Field(None, description="Parsed JSON payload if present")
    form: Dict[str, Optional[Any]] = Field(..., description="Form fields when multipart/form-data is used")


@app.post(
    "/api/journal-entries/_inspect",
    response_model=InspectResult,
    tags=["Journal Entries"],
    summary="Internal: inspect incoming request",
    description="Returns detected Content-Type and parsed form/body fields to debug payload shapes from the frontend.",
)
async def inspect_request(
    request: Request,
    payload: Optional[JournalEntryCreate] = Body(None),
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    image_remove: Optional[bool] = Form(None),
):
    """Return basic info about the request for debugging client payload issues."""
    try:
        ct = request.headers.get("content-type", "")
        return {
            "content_type": ct,
            "has_json_payload": payload is not None,
            "json_payload": payload.model_dump() if payload is not None else None,
            "form": {"title": title, "content": content, "image_remove": image_remove},
        }
    except Exception as exc:
        raise _structured_500("Inspection failed", {"exception": str(exc)})


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


def _delete_existing_file(image_url: Optional[str]) -> None:
    """
    If image_url points under /static/uploads, delete the corresponding file from disk.
    Silently ignore errors to avoid blocking request on filesystem issues.
    """
    if not image_url:
        return
    # image_url expected like "/static/uploads/<name>"
    try:
        prefix = "/static/uploads/"
        if image_url.startswith(prefix):
            filename = image_url[len(prefix):]
            if filename:
                path = os.path.join(UPLOADS_DIR, filename)
                if os.path.isfile(path):
                    os.remove(path)
    except Exception:
        # Do not raise; best effort cleanup
        pass


# PUBLIC_INTERFACE
@app.get("/", tags=["Health"], summary="Health Check")
def health_check():
    """Health check endpoint to verify service is running."""
    return {"message": "Healthy"}


def _structured_500(message: str, context: Optional[Dict[str, Any]] = None) -> HTTPException:
    """
    Build a structured HTTPException for 500 errors with optional context for debugging.
    """
    detail: Dict[str, Any] = {"error": message}
    if context:
        # Ensure context is JSON serializable
        safe_ctx: Dict[str, Any] = {}
        for k, v in context.items():
            try:
                str(v)  # attempt simple coercion for safety
                safe_ctx[k] = v
            except Exception:
                safe_ctx[k] = repr(v)
        detail["context"] = safe_ctx
    return HTTPException(status_code=500, detail=detail)


# PUBLIC_INTERFACE
@app.get(
    "/api/journal-entries",
    response_model=List[JournalEntryRead],
    tags=["Journal Entries"],
    summary="List journal entries",
    description="Returns a list of journal entries ordered by most recently updated. Supports optional case-insensitive substring search by title, and optional date-range filtering using start_date and end_date (YYYY-MM-DD).",
)
def list_journal_entries(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD), inclusive"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD), inclusive"),
    title: Optional[str] = Query(None, description="Case-insensitive substring to match in the title"),
):
    """
    List journal entries with optional title search and date-range filtering.

    Parameters:
    - title: optional case-insensitive substring to search in title
    - start_date: optional start date YYYY-MM-DD (inclusive)
    - end_date: optional end date YYYY-MM-DD (inclusive)

    Returns:
    - List of JournalEntryRead
    """
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    try:
        with get_session() as session:
            stmt = select(JournalEntry)

            # Build inclusive datetime bounds once
            start_dt: Optional[datetime] = None
            end_dt: Optional[datetime] = None
            if start_date:
                start_dt = datetime.combine(start_date, datetime.min.time())
            if end_date:
                # Use max time for inclusive end of day
                end_dt = datetime.combine(end_date, datetime.max.time())

            # Guard against null created_at before applying range bounds
            if start_dt is not None:
                stmt = stmt.where(JournalEntry.created_at != None)  # noqa: E711
                stmt = stmt.where(JournalEntry.created_at >= start_dt)
            if end_dt is not None:
                stmt = stmt.where(JournalEntry.created_at != None)  # noqa: E711
                stmt = stmt.where(JournalEntry.created_at <= end_dt)

            # Title search (case-insensitive substring on title)
            if title:
                t = title.strip()
                if t:
                    # Use SQLModel/SQLAlchemy ilike for case-insensitive match
                    stmt = stmt.where(JournalEntry.title.ilike(f"%{t}%"))

            # Always order by latest updated first
            stmt = stmt.order_by(JournalEntry.updated_at.desc())

            entries = session.exec(stmt).all()
            if not entries:
                return []

            # Ensure robustness if any row has nulls unexpectedly
            safe_entries: List[JournalEntryRead] = []
            for e in entries:
                # Skip rows missing essential timestamps to prevent .date() or serialization errors
                if not getattr(e, "created_at", None) or not getattr(e, "updated_at", None):
                    continue
                safe_entries.append(
                    JournalEntryRead(
                        id=e.id,
                        title=e.title,
                        content=e.content,
                        image_url=e.image_url,
                        created_at=e.created_at,
                        updated_at=e.updated_at,
                    )
                )
            # If all were filtered out due to nulls, still return []
            return safe_entries
    except HTTPException:
        raise
    except Exception as exc:
        # Return a structured 500 with error detail to aid debugging in preview
        raise _structured_500(
            "Failed to list journal entries",
            {
                "exception": str(exc),
                "title": title,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
        )





# PUBLIC_INTERFACE
@app.get(
    "/api/journal-entries/dates",
    tags=["Journal Entries"],
    summary="Get dates with entries",
    description="Returns the list of calendar dates (YYYY-MM-DD) that have entries within the provided inclusive date range.",
)
def get_dates_with_entries(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD), inclusive"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD), inclusive"),
):
    """
    Returns only the distinct dates that have at least one entry within the given inclusive range.
    Useful for calendar highlighting in the Angular app.
    """
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    try:
        with get_session() as session:
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())

            stmt = select(JournalEntry).where(
                JournalEntry.created_at != None,  # noqa: E711
                JournalEntry.created_at >= start_dt,
                JournalEntry.created_at <= end_dt,
            )
            entries = session.exec(stmt).all()

            days: Set[str] = set()
            if entries:
                for e in entries:
                    if getattr(e, "created_at", None):
                        days.add(e.created_at.date().isoformat())
        # Always return 200 with dates array (possibly empty)
        return {"dates": sorted(list(days))}
    except HTTPException:
        raise
    except Exception as exc:
        raise _structured_500(
            "Failed to fetch dates with entries",
            {
                "exception": str(exc),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )


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
    description="Create a journal entry. Accepts either application/json with {title, content} when no image is provided, or multipart/form-data with Form fields and optional image when uploading. Field names must be exactly 'title', 'content', 'image', 'image_remove'.",
)
async def create_journal_entry(
    # JSON path (when Content-Type is application/json)
    payload: Optional[JournalEntryCreate] = Body(
        None,
        description="JSON body with title and content (used when no image is provided)",
    ),
    # Multipart path (when Content-Type is multipart/form-data)
    title: Optional[str] = Form(
        None, description="Title for the journal entry (1..200 chars)"
    ),
    content: Optional[str] = Form(
        None, description="Content/body for the entry (0..10000 chars); may be empty"
    ),
    image: Optional[UploadFile] = File(None, description="Optional image file"),
    image_remove: Optional[bool] = Form(
        False,
        description="Set true to explicitly remove an already-attached image (not typical on create).",
    ),
):
    """
    Create a new journal entry.

    Supports:
    - application/json: payload with 'title' and optional 'content' (no image)
    - multipart/form-data: Form fields 'title', 'content' and optional file field 'image'; optional 'image_remove' boolean
    """
    now = datetime.utcnow()

    try:
        # Prefer JSON mode when payload provided (Angular sends application/json when no image)
        if payload is not None:
            in_title = (payload.title or "").strip()
            if not in_title:
                # Match FastAPI validation error shape
                raise HTTPException(
                    status_code=422,
                    detail=[{"loc": ["body", "title"], "msg": "Field required", "type": "value_error"}],
                )
            in_content = (payload.content or "").strip()
        else:
            # Multipart mode (Angular sends multipart/form-data when image selected)
            if title is None or not str(title).strip():
                raise HTTPException(
                    status_code=422,
                    detail=[{"loc": ["form", "title"], "msg": "Field required", "type": "value_error.missing"}],
                )
            in_title = str(title).strip()
            in_content = (content or "").strip()

        image_url: Optional[str] = None
        # image_remove on create is typically ignored; if a file present, save it
        if image is not None:
            image_url = _save_upload(image)

        entry = JournalEntry(
            title=in_title,
            content=in_content,
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
    except HTTPException:
        # Let structured 422/4xx bubble up
        raise
    except Exception as exc:
        # Wrap unexpected errors
        raise _structured_500("Failed to create journal entry", {"exception": str(exc)})


# PUBLIC_INTERFACE
@app.put(
    "/api/journal-entries/{entry_id}",
    response_model=JournalEntryRead,
    tags=["Journal Entries"],
    summary="Update a journal entry",
    description="Update the title and/or content. Accepts either application/json with partial fields when no file is uploaded, or multipart/form-data with optional image to replace or remove (send image_remove=true). Field names: 'title', 'content', 'image', 'image_remove'.",
)
async def update_journal_entry(
    entry_id: int = Path(..., description="The ID of the journal entry to update", ge=1),
    # JSON path
    payload: Optional[JournalEntryUpdate] = Body(
        None,
        description="JSON body with fields to update when not uploading an image",
    ),
    # Multipart path
    title: Optional[str] = Form(None, description="Updated title (1..200 chars)"),
    content: Optional[str] = Form(None, description="Updated content (0..10000 chars)"),
    image: Optional[UploadFile] = File(None, description="Optional image file to replace existing"),
    image_remove: Optional[bool] = Form(False, description="Set true to remove existing image"),
):
    """Update existing journal entry with optional image replacement/removal. Accepts JSON or multipart."""
    try:
        with get_session() as session:
            entry = session.get(JournalEntry, entry_id)
            if entry is None:
                raise HTTPException(status_code=404, detail="Journal entry not found")

            updated = False

            # Prefer JSON mode when JSON payload provided and no file uploaded
            json_mode = payload is not None and image is None

            if json_mode:
                if payload.title is not None:
                    t = payload.title.strip()
                    if not t:
                        raise HTTPException(
                            status_code=422,
                            detail=[{"loc": ["body", "title"], "msg": "Title must not be empty", "type": "value_error"}],
                        )
                    if t != entry.title:
                        entry.title = t
                        updated = True
                if payload.content is not None:
                    c = payload.content.strip()
                    if c != entry.content:
                        entry.content = c
                        updated = True
                # No image ops in JSON mode
            else:
                # Multipart mode
                if title is not None:
                    t = title.strip()
                    if not t:
                        raise HTTPException(
                            status_code=422,
                            detail=[{"loc": ["form", "title"], "msg": "Title must not be empty", "type": "value_error"}],
                        )
                    if t != entry.title:
                        entry.title = t
                        updated = True

                if content is not None:
                    c = content.strip()
                    if c != entry.content:
                        entry.content = c
                        updated = True

                if image_remove:
                    if entry.image_url:
                        _delete_existing_file(entry.image_url)
                        entry.image_url = None
                        updated = True

                if image is not None:
                    if entry.image_url:
                        _delete_existing_file(entry.image_url)
                    entry.image_url = _save_upload(image)
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
    except HTTPException:
        raise
    except Exception as exc:
        raise _structured_500("Failed to update journal entry", {"exception": str(exc), "entry_id": entry_id})


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
        # attempt to delete any associated file
        if entry.image_url:
            _delete_existing_file(entry.image_url)
        session.delete(entry)
        session.flush()
    # Return empty 204 response
    return Response(status_code=204)
