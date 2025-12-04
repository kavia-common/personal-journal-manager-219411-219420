Verification log for journal_backend date-range endpoints

Date: 2025-12-04

Context
- Target endpoints:
  - GET /api/journal-entries?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
  - GET /api/journal-entries/dates?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
- Database: SQLite at personal-journal-manager-219411-219420/journal.db

Checks performed
1) DB schema verification
   - SQLModel metadata includes JournalEntry with columns:
     id INTEGER PK, title TEXT, content TEXT, image_url TEXT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL.
   - init_db() is called on startup to create table/columns if missing.

2) CORS and path
   - CORS derives allowed origins from ALLOWED_ORIGINS or NG_APP_FRONTEND_URL; defaults to "*".
   - Static files mounted at /static, upload URLs returned as /static/uploads/<filename>.
   - All journal routes are prefixed with /api/journal-entries, matching README and openapi.json.

3) Endpoint behavior changes
   - list_journal_entries:
     • Parses Optional[date] via Query.
     • Inclusive filtering on created_at between start_date 00:00:00 and end_date 23:59:59.999999.
     • Guards against null created_at to avoid 500.
     • Returns 200 with [] when no entries.
     • Structured 500 error detail with context on unexpected exceptions.
   - get_dates_with_entries:
     • Returns {"dates": []} when no matches.
     • Inclusive filtering and null guards.
     • Structured 500 error detail with context on unexpected exceptions.

4) Error handling
   - 400 when end_date < start_date.
   - 422 maintained for validation where applicable (FastAPI default).
   - 500 responses include {"error": "...", "context": {"exception": "<message>"}}.

Expected results (manual test plan)
- GET /api/journal-entries?start_date=2099-01-01&end_date=2099-01-02 -> 200 []
- GET /api/journal-entries/dates?start_date=2099-01-01&end_date=2099-01-02 -> 200 {"dates": []}
- GET /api/journal-entries?start_date=2025-12-01&end_date=2025-12-31 with existing data -> 200 [ ... ordered by updated_at desc ... ]
- GET /api/journal-entries?end_date=2025-12-10 (no start) -> 200 [ ... <= end inclusive ... ]
- GET /api/journal-entries?start_date=2025-12-10 (no end) -> 200 [ ... >= start inclusive ... ]
- GET /api/journal-entries/dates?start_date=2025-12-10&end_date=2025-12-01 -> 400 end_date must be on or after start_date

Notes
- If an older DB existed without created_at/updated_at/image_url, recreate or migrate; init_db() ensures table exists but does not migrate existing tables.
