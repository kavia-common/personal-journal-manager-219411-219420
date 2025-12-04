from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlmodel import SQLModel, Field as SQLField


# Database Models
class JournalEntry(SQLModel, table=True):
    """SQLModel table for journal entries with optional image URL."""
    id: Optional[int] = SQLField(default=None, primary_key=True, index=True)
    title: str = SQLField(index=True, min_length=1, max_length=200)
    content: str = SQLField(min_length=1, max_length=10_000)
    image_url: Optional[str] = SQLField(default=None, nullable=True)  # path/URL to the uploaded image
    created_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False)


# PUBLIC_INTERFACE
class JournalEntryCreate(BaseModel):
    """Payload model to create a new journal entry."""
    title: str = Field(..., min_length=1, max_length=200, description="Title for the journal entry (1..200 chars)")
    content: str = Field(..., min_length=1, max_length=10_000, description="Content/body for the entry (1..10000 chars)")

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Title must not be empty")
        return s

    @field_validator("content")
    @classmethod
    def strip_content(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Content must not be empty")
        return s


# PUBLIC_INTERFACE
class JournalEntryUpdate(BaseModel):
    """Payload model to update an existing journal entry."""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Updated title (1..200 chars)")
    content: Optional[str] = Field(None, min_length=1, max_length=10_000, description="Updated content (1..10000 chars)")

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        s = v.strip()
        if not s:
            raise ValueError("Title must not be empty")
        return s

    @field_validator("content")
    @classmethod
    def strip_content(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        s = v.strip()
        if not s:
            raise ValueError("Content must not be empty")
        return s


# PUBLIC_INTERFACE
class JournalEntryRead(BaseModel):
    """Response model for a journal entry."""
    id: int = Field(..., description="Entry identifier")
    title: str = Field(..., description="Entry title")
    content: str = Field(..., description="Entry content")
    image_url: Optional[str] = Field(None, description="Public URL path to the attached image")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")
