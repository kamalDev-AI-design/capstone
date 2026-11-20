from fastapi import APIRouter, Depends

from psit import __version__
from psit.contracts.reports import HealthOut

from ..deps import get_svc

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(svc=Depends(get_svc)):
    from ..app import db_ok
    return HealthOut(status="ok", version=__version__, database="ok" if db_ok(svc.engine) else "error")
