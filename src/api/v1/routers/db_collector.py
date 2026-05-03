"""DB Collector router — functional CRUD + run."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.db_collector import DbSourceCreate, DbSourceUpdate, DbSourceOut
from src.core.deps import get_db, get_current_user_id
from src.core.exceptions import NotFoundError
from src.services.db_source_service import DbSourceService

router = APIRouter(prefix="/db-sources", tags=["db-collector"])


@router.get("", response_model=list[DbSourceOut])
async def list_db_sources(
    session: AsyncSession = Depends(get_db),
):
    service = DbSourceService(session)
    return await service.list_sources()


@router.post("", response_model=DbSourceOut, status_code=201)
async def create_db_source(
    data: DbSourceCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = DbSourceService(session)
    return await service.create_source(data)


@router.post("/{source_id}/run", response_model=DbSourceOut)
async def run_db_source(
    source_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = DbSourceService(session)
    return await service.run_source(source_id)


@router.delete("/{source_id}", status_code=204)
async def delete_db_source(
    source_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = DbSourceService(session)
    await service.delete_source(source_id)
