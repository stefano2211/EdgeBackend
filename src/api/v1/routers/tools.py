"""Tools router — stub (Fase 6)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
async def list_tools():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Tool endpoints will be implemented in Fase 6",
    )


@router.post("")
async def create_tool():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Tool endpoints will be implemented in Fase 6",
    )


@router.get("/sources")
async def list_sources():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Tool endpoints will be implemented in Fase 6",
    )


@router.post("/sources")
async def create_source():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Tool endpoints will be implemented in Fase 6",
    )


@router.post("/discover")
async def discover_tools():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Tool endpoints will be implemented in Fase 6",
    )
