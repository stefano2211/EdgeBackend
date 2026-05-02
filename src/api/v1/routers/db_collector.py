"""DB Collector router — stub (Fase 7)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/db-sources", tags=["db-collector"])


@router.get("")
async def list_db_sources():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="DB Collector endpoints will be implemented in Fase 7",
    )


@router.post("")
async def create_db_source():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="DB Collector endpoints will be implemented in Fase 7",
    )


@router.post("/{source_id}/run")
async def run_db_source(source_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="DB Collector endpoints will be implemented in Fase 7",
    )


@router.delete("/{source_id}")
async def delete_db_source(source_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="DB Collector endpoints will be implemented in Fase 7",
    )
