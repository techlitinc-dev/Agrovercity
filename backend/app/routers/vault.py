# never log Aadhaar numbers or file bytes
import logging

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app.core import db
from app.core.deps import current_user_id
from app.services import storage as storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vault", tags=["vault"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_SIZE_BYTES = 5 * 1024 * 1024


def _docs_path(uid: str) -> str:
    return f"users/{uid}/vault_documents"


@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), docType: str = Form(...), uid: str = Depends(current_user_id)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": "Only JPEG, PNG and PDF files are allowed", "fieldErrors": {}},
        )
    data = await file.read()
    if len(data) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": "File exceeds the 5 MB limit", "fieldErrors": {}},
        )
    blob_path, size = storage_service.upload_user_file(uid, data, file.filename or "upload", file.content_type, prefix="vault")
    doc_id = uuid4().hex
    doc = {
        "id": doc_id,
        "docType": docType,
        "fileName": file.filename or "upload",
        "blobPath": blob_path,
        "uploadedAt": datetime.now(timezone.utc).isoformat(),
        "sizeBytes": size,
    }
    await db.set_subdoc_at(_docs_path(uid), doc_id, doc)
    return {
        "id": doc_id,
        "docType": docType,
        "fileName": doc["fileName"],
        "downloadUrl": storage_service.signed_download_url(blob_path),
        "uploadedAt": doc["uploadedAt"],
        "sizeBytes": size,
    }


@router.get("/documents")
async def list_documents(page: int = 1, pageSize: int = 20, uid: str = Depends(current_user_id)):
    docs = await db.list_subdocs(_docs_path(uid))
    docs.sort(key=lambda d: d.get("uploadedAt", ""), reverse=True)
    items = [
        {
            "id": d["id"],
            "docType": d.get("docType"),
            "fileName": d.get("fileName"),
            "downloadUrl": storage_service.signed_download_url(d.get("blobPath", "")),
            "uploadedAt": d.get("uploadedAt"),
            "sizeBytes": d.get("sizeBytes", 0),
        }
        for d in docs
    ]
    total = len(items)
    page_size = max(1, min(pageSize, 50))
    start = (max(1, page) - 1) * page_size
    return {"data": items[start : start + page_size], "page": page, "pageSize": page_size, "total": total}


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: str, uid: str = Depends(current_user_id)):
    doc = await db.get_subdoc_at(_docs_path(uid), document_id)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document not found", "fieldErrors": {}},
        )
    storage_service.delete_blob(doc.get("blobPath", ""))
    await db.delete_subdoc_at(_docs_path(uid), document_id)
    return Response(status_code=204)
