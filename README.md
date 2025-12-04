# personal-journal-manager-219411-219420

Backend updated to support optional image attachments for journal entries:
- Accepts multipart/form-data on POST /api/journal-entries and PUT /api/journal-entries/{id}
- Field names: title (string), content (string), image (file, optional), image_remove (boolean, optional on update)
- Stores files under /static/uploads and serves via GET /static/uploads/{filename}
- Responses include image_url when present

Frontend (Angular) should:
- Use environment API base URL for requests and image URLs
- Send FormData for create/update when an image is selected
- Support image replace (send new image) and remove (set image_remove=true)
- Display image thumbnail when image_url is present
