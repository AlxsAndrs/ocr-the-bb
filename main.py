import asyncio
import os
import tempfile
from pathlib import Path

import ocrmypdf
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from jobs import JobStatus, JobStore

DEFAULT_LANGUAGES = os.environ.get("OCR_LANGUAGES", "eng+fra")
MAX_WORKERS = int(os.environ.get("OCR_MAX_WORKERS", "2"))
RESULT_TTL_SECONDS = int(os.environ.get("OCR_RESULT_TTL", "3600"))
CLEANUP_INTERVAL_SECONDS = 300

app = FastAPI(title="OCR Service", version="2.0.0")
store = JobStore(max_workers=MAX_WORKERS, result_ttl_seconds=RESULT_TTL_SECONDS)


@app.on_event("startup")
async def start_cleanup_loop():
    async def loop():
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            store.cleanup_expired()

    asyncio.create_task(loop())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ocr")
def ocr(
    file: UploadFile = File(...),
    languages: str = Query(default=DEFAULT_LANGUAGES),
    force: bool = Query(default=False),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="ocr_"))
    input_path = tmp_dir / "input.pdf"
    output_path = tmp_dir / "output.pdf"

    with input_path.open("wb") as f:
        f.write(file.file.read())

    try:
        ocrmypdf.ocr(
            input_path,
            output_path,
            language=languages,
            force_ocr=force,
            skip_text=not force,
            progress_bar=False,
        )
    except ocrmypdf.exceptions.PriorOcrFoundError:
        raise HTTPException(
            status_code=409,
            detail="Document already contains text. Retry with force=true to re-OCR.",
        )
    except ocrmypdf.exceptions.EncryptedPdfError:
        raise HTTPException(status_code=422, detail="Encrypted PDF is not supported.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}")

    out_name = Path(file.filename).stem + "_ocr.pdf"
    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=out_name,
    )


@app.post("/ocr/jobs")
def create_jobs(
    files: list[UploadFile] = File(...),
    languages: str = Query(default=DEFAULT_LANGUAGES),
    force: bool = Query(default=False),
):
    pdfs = [f for f in files if f.filename.lower().endswith(".pdf")]
    if not pdfs:
        raise HTTPException(status_code=400, detail="No PDF files in the request.")

    batch_id = store.create_batch()
    jobs_out = []

    for f in pdfs:
        tmp_dir = Path(tempfile.mkdtemp(prefix="ocr_"))
        input_path = tmp_dir / "input.pdf"
        output_path = tmp_dir / "output.pdf"
        with input_path.open("wb") as out:
            out.write(f.file.read())

        job = store.add_job(
            batch_id=batch_id,
            filename=f.filename,
            input_path=input_path,
            output_path=output_path,
            languages=languages,
            force=force,
        )
        jobs_out.append({"job_id": job.job_id, "filename": job.filename})

    return {"batch_id": batch_id, "jobs": jobs_out}


@app.get("/ocr/jobs/{batch_id}")
def batch_status(batch_id: str):
    jobs = store.get_batch(batch_id)
    if jobs is None:
        raise HTTPException(status_code=404, detail="Batch not found.")

    return {
        "batch_id": batch_id,
        "jobs": [
            {
                "job_id": j.job_id,
                "filename": j.filename,
                "status": j.status.value,
                "error": j.error,
            }
            for j in jobs
        ],
    }


@app.get("/ocr/jobs/{batch_id}/files/{job_id}")
def download_result(batch_id: str, job_id: str):
    job = store.get_job(job_id)
    if job is None or job.batch_id != batch_id:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status == JobStatus.FAILED:
        raise HTTPException(status_code=422, detail=job.error or "OCR failed.")
    if job.status != JobStatus.DONE:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not ready (status: {job.status.value}).",
        )
    if not job.output_path.exists():
        raise HTTPException(status_code=410, detail="Result has expired.")

    out_name = Path(job.filename).stem + "_ocr.pdf"
    return FileResponse(
        job.output_path,
        media_type="application/pdf",
        filename=out_name,
    )
