from datetime import date, datetime, timedelta
from typing import List, Optional, Set

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# In-memory storage for demo purposes
# In a real project, replace with DB models/ORM
class JournalEntryDTO(BaseModel):
    id: int = Field(..., description="Unique identifier")
    title: str = Field(..., description="Entry title")
    content: str = Field(..., description="Entry content")
    imageUrl: Optional[str] = Field(None, description="Relative or absolute image URL")
    created_at: datetime = Field(..., description="Creation timestamp in ISO format")
    updated_at: datetime = Field(..., description="Last update timestamp in ISO format")


class CreateJournalEntryDTO(BaseModel):
    title: str = Field(..., description="Entry title")
    content: str = Field(..., description="Entry content")


class UpdateJournalEntryDTO(BaseModel):
    title: Optional[str] = Field(None, description="Entry title")
    content: Optional[str] = Field(None, description="Entry content")


# Fake store
_store: List[JournalEntryDTO] = []
_next_id = 1


def _seed():
    global _next_id
    if _store:
        return
    base = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
    samples = [
        ("First Day", "Kickoff thoughts", 0),
        ("Deep Work", "Made progress on project", -2),
        ("Weekend Note", "Relaxed and read a book", -5),
        ("Mid-month", "Met with the team", -14),
        ("End month", "Planning next goals", -27),
    ]
    for title, content, offset in samples:
        created = base + timedelta(days=offset)
        entry = JournalEntryDTO(
            id=_next_id,
            title=title,
            content=content,
            imageUrl=None,
            created_at=created,
            updated_at=created,
        )
        _store.append(entry)
        _next_id += 1


app = FastAPI(
    title="Journal Backend API",
    description="FastAPI backend for personal journal manager with date-range support for calendar views.",
    version="1.1.0",
    openapi_tags=[
        {"name": "journal-entries", "description": "CRUD and date-range queries for journal entries"},
    ],
)

# Allow all origins for local dev and preview; adjust in production via env
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with env-configured origin list in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_seed()


# PUBLIC_INTERFACE
@app.get("/api/journal-entries", response_model=List[JournalEntryDTO], tags=["journal-entries"], summary="List journal entries", description="List journal entries. Supports optional date-range filtering using start_date and end_date (YYYY-MM-DD). Returns entries whose created_at date falls within the inclusive range.")
def list_entries(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD), inclusive"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD), inclusive"),
) -> List[JournalEntryDTO]:
    """
    Backend route to list journal entries with optional date-range filtering.

    Parameters:
    - start_date: optional start date in YYYY-MM-DD
    - end_date: optional end date in YYYY-MM-DD

    Returns:
    - List of JournalEntryDTO
    """
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    # Without filters return all, sorted by updated_at desc
    if not start_date and not end_date:
        return sorted(_store, key=lambda e: e.updated_at, reverse=True)

    # Filter by date range on created_at.date()
    def in_range(e: JournalEntryDTO) -> bool:
        d = e.created_at.date()
        if start_date and d < start_date:
            return False
        if end_date and d > end_date:
            return False
        return True

    filtered = [e for e in _store if in_range(e)]
    return sorted(filtered, key=lambda e: e.updated_at, reverse=True)


class DatesWithEntriesResponse(BaseModel):
    dates: List[date] = Field(..., description="List of calendar dates (YYYY-MM-DD) that have at least one entry")


# PUBLIC_INTERFACE
@app.get(
    "/api/journal-entries/dates",
    response_model=DatesWithEntriesResponse,
    tags=["journal-entries"],
    summary="Get dates with entries",
    description="Optimized endpoint that returns only the list of dates that have entries within the provided range. Use to efficiently highlight calendar days.",
)
def get_dates_with_entries(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD), inclusive"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD), inclusive"),
) -> DatesWithEntriesResponse:
    """
    Returns only the dates which have entries within the given inclusive date range.
    Useful for calendar heatmap/highlights.
    """
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    days: Set[date] = set()
    for e in _store:
        d = e.created_at.date()
        if start_date <= d <= end_date:
            days.add(d)
    return DatesWithEntriesResponse(dates=sorted(days))


# PUBLIC_INTERFACE
@app.get("/api/journal-entries/{entry_id}", response_model=JournalEntryDTO, tags=["journal-entries"], summary="Get entry by id", description="Fetch a single journal entry by its ID")
def get_entry(entry_id: int) -> JournalEntryDTO:
    for e in _store:
        if e.id == entry_id:
            return e
    raise HTTPException(status_code=404, detail="Not found")


# PUBLIC_INTERFACE
@app.post("/api/journal-entries", response_model=JournalEntryDTO, tags=["journal-entries"], summary="Create entry", description="Create a new journal entry")
def create_entry(payload: CreateJournalEntryDTO) -> JournalEntryDTO:
    global _next_id
    now = datetime.utcnow()
    entry = JournalEntryDTO(
        id=_next_id,
        title=payload.title,
        content=payload.content,
        imageUrl=None,
        created_at=now,
        updated_at=now,
    )
    _store.append(entry)
    _next_id += 1
    return entry


# PUBLIC_INTERFACE
@app.put("/api/journal-entries/{entry_id}", response_model=JournalEntryDTO, tags=["journal-entries"], summary="Update entry", description="Update title/content of an existing journal entry")
def update_entry(entry_id: int, payload: UpdateJournalEntryDTO) -> JournalEntryDTO:
    for e in _store:
        if e.id == entry_id:
            if payload.title is not None:
                e.title = payload.title
            if payload.content is not None:
                e.content = payload.content
            e.updated_at = datetime.utcnow()
            return e
    raise HTTPException(status_code=404, detail="Not found")


# PUBLIC_INTERFACE
@app.delete("/api/journal-entries/{entry_id}", tags=["journal-entries"], summary="Delete entry", description="Delete a journal entry by ID")
def delete_entry(entry_id: int) -> dict:
    idx = next((i for i, x in enumerate(_store) if x.id == entry_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Not found")
    _store.pop(idx)
    return {"status": "ok"}
