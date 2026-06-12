from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from forge.uploads import UploadService

router = APIRouter(prefix="/api/uploads")

_service: UploadService | None = None


def set_service(service: UploadService) -> None:
    global _service
    _service = service


def _svc() -> UploadService:
    if _service is None:
        raise HTTPException(status_code=503, detail="Upload service not configured")
    return _service


@router.post("")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    path = _svc().save_file(content, file.filename or "")
    return {"path": str(path), "filename": path.name}


@router.get("/latest")
async def get_latest():
    path = _svc().get_latest()
    if path is None:
        raise HTTPException(status_code=404, detail="No uploads found")
    return {"path": str(path), "filename": path.name}
