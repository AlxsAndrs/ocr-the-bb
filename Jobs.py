import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import ocrmypdf


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    batch_id: str
    filename: str
    input_path: Path
    output_path: Path
    languages: str
    force: bool
    status: JobStatus = JobStatus.QUEUED
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None


class JobStore:
    def __init__(self, max_workers: int = 2, result_ttl_seconds: int = 3600):
        self._jobs: dict[str, Job] = {}
        self._batches: dict[str, list[str]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._result_ttl = result_ttl_seconds

    def create_batch(self) -> str:
        batch_id = uuid.uuid4().hex
        with self._lock:
            self._batches[batch_id] = []
        return batch_id

    def add_job(
        self,
        batch_id: str,
        filename: str,
        input_path: Path,
        output_path: Path,
        languages: str,
        force: bool,
    ) -> Job:
        job_id = uuid.uuid4().hex
        job = Job(
            job_id=job_id,
            batch_id=batch_id,
            filename=filename,
            input_path=input_path,
            output_path=output_path,
            languages=languages,
            force=force,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._batches.setdefault(batch_id, []).append(job_id)
        self._executor.submit(self._run, job_id)
        return job

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = JobStatus.PROCESSING

        try:
            ocrmypdf.ocr(
                job.input_path,
                job.output_path,
                language=job.languages,
                force_ocr=job.force,
                skip_text=not job.force,
                progress_bar=False,
            )
            new_status = JobStatus.DONE
            error = None
        except ocrmypdf.exceptions.PriorOcrFoundError:
            new_status = JobStatus.FAILED
            error = "Document already contains text. Retry with force=true to re-OCR."
        except ocrmypdf.exceptions.EncryptedPdfError:
            new_status = JobStatus.FAILED
            error = "Encrypted PDF is not supported."
        except Exception as exc:
            new_status = JobStatus.FAILED
            error = f"OCR failed: {exc}"

        with self._lock:
            job.status = new_status
            job.error = error
            job.finished_at = time.time()

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def get_batch(self, batch_id: str) -> Optional[list[Job]]:
        with self._lock:
            job_ids = self._batches.get(batch_id)
            if job_ids is None:
                return None
            return [self._jobs[jid] for jid in job_ids]

    def cleanup_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                jid
                for jid, job in self._jobs.items()
                if job.finished_at is not None
                and now - job.finished_at > self._result_ttl
            ]
            for jid in expired:
                job = self._jobs.pop(jid)
                for p in (job.input_path, job.output_path):
                    try:
                        if p.exists():
                            p.unlink()
                    except OSError:
                        pass
                batch = self._batches.get(job.batch_id)
                if batch and jid in batch:
                    batch.remove(jid)
            empty_batches = [
                bid for bid, jids in self._batches.items() if not jids
            ]
            for bid in empty_batches:
                self._batches.pop(bid, None)
