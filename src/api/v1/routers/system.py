"""System stats endpoint."""

from fastapi import APIRouter

from src.api.v1.schemas.system import SystemStats
from src.ia.llm_client import get_llm_client

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/stats", response_model=SystemStats)
async def get_stats() -> SystemStats:
    # Placeholder: real implementation will query DB in later phases
    client = get_llm_client()
    return SystemStats(
        active_users=0,
        total_conversations=0,
        status="healthy" if client.provider else "no_llm",
    )
