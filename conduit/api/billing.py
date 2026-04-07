from fastapi import APIRouter
router = APIRouter()

@router.get("/usage", summary="Per-connection usage")
async def usage(conn_id: str | None = None): return {"status": "planned"}

@router.get("/chargeback", summary="Team chargeback by SaaS provider")
async def chargeback(team: str | None = None, saas: str | None = None): return {"status": "planned"}
