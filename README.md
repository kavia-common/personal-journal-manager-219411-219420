# personal-journal-manager-219411-219420

Backend updates:
- Supports optional image attachments on POST/PUT /api/journal-entries
- Serves files under /static/uploads; responses include image_url when present
- Date-range support on GET /api/journal-entries via start_date and end_date (YYYY-MM-DD)
- Dedicated endpoint GET /api/journal-entries/dates?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD returns {"dates": ["YYYY-MM-DD", ...]}

CORS configuration:
- Configure allowed origins via ALLOWED_ORIGINS (comma-separated). Defaults to "*" for development.
- Legacy NG_APP_FRONTEND_URL is also supported if ALLOWED_ORIGINS is not set.

Example requests:
- GET /api/journal-entries?start_date=2025-12-01&end_date=2025-12-31 -> 200 JSON array
- GET /api/journal-entries/dates?start_date=2025-12-01&end_date=2025-12-31 -> 200 {"dates":[...]}

Frontend (Angular) should:
- Use environment API base URL for requests and image URLs
- Send FormData for create/update when an image is selected
- Support image replace (send new image) and remove (set image_remove=true)
- Display image thumbnail when image_url is present
