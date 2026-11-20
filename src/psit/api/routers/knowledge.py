from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from psit.contracts.knowledge import (
    DocumentOverview, IndexStatus, IngestResult, KnowledgeAnswer, KnowledgeSearchRequest,
)
from psit.rag.vector_index import IndexMismatchError

from ..deps import get_actor, get_request_id, get_svc

router = APIRouter(tags=["knowledge"])


@router.post("/knowledge/search", response_model=KnowledgeAnswer)
def search(body: KnowledgeSearchRequest, svc=Depends(get_svc), actor=Depends(get_actor), rid=Depends(get_request_id)):
    try:
        return KnowledgeAnswer(**svc.knowledge.search(body.model_dump(mode="python"), actor, rid))
    except IndexMismatchError as e:
        raise HTTPException(409, {"error": {"code": "INDEX_REBUILD_REQUIRED", "message": str(e)}})


@router.get("/knowledge/index", response_model=IndexStatus)
def index_status(svc=Depends(get_svc), actor=Depends(get_actor)):
    return IndexStatus(**svc.index.status())


@router.post("/knowledge/index/rebuild", response_model=IndexStatus)
def rebuild(svc=Depends(get_svc), actor=Depends(get_actor), rid=Depends(get_request_id)):
    return IndexStatus(**svc.index.rebuild(actor, rid))


@router.get("/documents", response_model=DocumentOverview)
def documents(svc=Depends(get_svc), actor=Depends(get_actor)):
    o = svc.ingestion.overview()
    return DocumentOverview(
        versions=o["versions"],
        runs=[{"id": r.id, "filename": r.filename, "status": r.status, "message": r.message,
               "chunk_count": r.chunk_count, "started_at": r.started_at} for r in o["runs"]])


@router.post("/documents", response_model=IngestResult)
async def upload(file: UploadFile = File(...), rebuild: bool = Query(True), svc=Depends(get_svc),
                 actor=Depends(get_actor), rid=Depends(get_request_id)):
    data = await file.read()
    result = svc.ingestion.ingest(file.filename or "upload", data, actor, rid)
    if rebuild and result["status"] == "INGESTED":
        svc.index.rebuild(actor, rid)
    return IngestResult(**result)
