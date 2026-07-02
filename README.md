# ocr-api

Synchronous REST API for OCR. Upload a PDF, get back an OCR'd PDF with a
searchable text layer, powered by OCRmyPDF.

## Setup

```
docker compose up --build
```

The service listens on port 8000. Interactive API docs are auto-generated at
`http://<host>:8000/docs`.

## Endpoints

### `GET /health`
Liveness check. Returns `{"status": "ok"}`.

### `POST /ocr`
Upload a PDF, receive the OCR'd PDF in the response body.

Query parameters:
- `languages` — tesseract language codes joined with `+` (default: `eng+fra`).
- `force` — set `true` to re-OCR documents that already contain text
  (default: `false`, which skips pages that already have a text layer).

## Examples

```
# basic
curl -X POST http://localhost:8000/ocr \
  -F "file=@document.pdf" \
  -o document_ocr.pdf

# specify languages
curl -X POST "http://localhost:8000/ocr?languages=eng+deu" \
  -F "file=@document.pdf" \
  -o document_ocr.pdf

# force re-OCR of a document that already has text
curl -X POST "http://localhost:8000/ocr?force=true" \
  -F "file=@document.pdf" \
  -o document_ocr.pdf
```

## Notes

- Synchronous: the connection stays open until OCR completes. For large scanned
  documents this may take a while; an async job-based version is a planned
  follow-up.
- Only `.pdf` files are accepted.
