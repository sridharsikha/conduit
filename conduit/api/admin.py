from fastapi import APIRouter
router = APIRouter()

@router.post("/teams", summary="Register a team")
async def register_team(): return {"status": "planned"}

@router.post("/teams/{team}/accounts", summary="Register cloud account")
async def register_account(team: str): return {"status": "planned"}

@router.post("/teams/{team}/validate", summary="Run pre-flight validation")
async def validate_team(team: str): return {"status": "planned"}
