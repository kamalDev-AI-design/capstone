from fastapi import APIRouter, Depends

from psit.services.seed import load_demo_data

from ..deps import get_actor, get_svc

router = APIRouter(prefix="/admin", tags=["admin (demo only)"])


@router.post("/seed")
def seed(svc=Depends(get_svc), actor=Depends(get_actor)):
    """Loads fictional demo reports if the database is empty."""
    return {"created": load_demo_data(svc.intake, svc.workflow, svc.approvals)}
