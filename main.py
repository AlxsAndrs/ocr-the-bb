import os
import tempfile
from pathlib import Path

import ocrmypdf
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

DEFAULT_LANGUAGES = os.environ.get("OCR_LANGUAGES", "eng+fra")

app = FastAPI(title="OCR Service", version="1.0.0")


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
