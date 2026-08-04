from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter()
RAW_PDF_DIR = os.path.join(os.path.dirname(__file__), "../data/raw_pdfs")

@router.get("/download/{filename}")
def download_pdf(filename: str):
    safe = os.path.basename(filename)  # prevent path traversal
    path = os.path.join(RAW_PDF_DIR, safe)
    if not os.path.exists(path):
        return {"error": "File not found"}
    return FileResponse(path, media_type="application/pdf",
                        filename=safe)

@router.get("/view/{filename}")
def view_pdf(filename: str):
    safe = os.path.basename(filename)
    path = os.path.join(RAW_PDF_DIR, safe)
    if not os.path.exists(path):
        return {"error": "File not found"}
    return FileResponse(path, media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={safe}"})
