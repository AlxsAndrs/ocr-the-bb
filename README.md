# ocr-api

REST API for OCR, powered by OCRmyPDF. Supports both synchronous single-file
OCR and asynchronous batch jobs.

## Setup

```
docker compose up --build
```

The service listens on container port 8000, published on host port 8100 by
default (change in `docker-compose.yml`). Interactive docs at
`http://<host>:8100/docs`.

## Configuration (all optional)

- `OCR_LANGUAGES` — default tesseract languages, `+`-joined (default `eng+fra`).
- `OCR_MAX_WORKERS` — concurrent OCR jobs for the async queue (default `2`).
- `OCR_RESULT_TTL` — seconds to keep finished results before cleanup
  (default `3600`).

## Endpoints

### `GET /health`
Liveness check.

### `POST /ocr` (synchronous)
Upload one PDF, get the OCR'd PDF back in the response. Blocks until done.
Query params: `languages`, `force`.

### `POST /ocr/jobs` (asynchronous, batch)
Upload one or more PDFs (repeat the `files` field). Returns immediately with a
`batch_id` and a `job_id` per file. Query params: `languages`, `force`.

### `GET /ocr/jobs/{batch_id}`
Status of every file in the batch: `queued`, `processing`, `done`, or `failed`
(with an error message on failure).

### `GET /ocr/jobs/{batch_id}/files/{job_id}`
Download one finished result. Returns 409 if not ready, 422 if that file
failed, 410 if the result has expired past its TTL.

## Examples

```
# synchronous single file
curl -X POST http://<host>:8100/ocr \
  -F "file=@document.pdf" -o document_ocr.pdf

# submit an async batch
curl -X POST "http://<host>:8100/ocr/jobs?languages=eng+fra" \
  -F "files=@a.pdf" -F "files=@b.pdf" -F "files=@c.pdf"

# check batch status
curl http://<host>:8100/ocr/jobs/<batch_id>

# download one finished result
curl http://<host>:8100/ocr/jobs/<batch_id>/files/<job_id> -o a_ocr.pdf
```

## Notes

- Jobs and results are held in memory / temp storage inside the container.
  A restart clears queued jobs and finished results — acceptable for an
  internal service. If durability across restarts is needed, back the queue
  with Redis and a separate worker.
- Only `.pdf` files are accepted; non-PDF uploads in a batch are ignored.
