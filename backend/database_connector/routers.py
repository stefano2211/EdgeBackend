from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database_connector.schemas import (
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
    DatabaseConnectionOut,
    SchemaDiscoveryResult,
    SchemaEnrichment,
    QueryRequest,
    QueryResult,
    SupportedDbType,
)
from backend.database_connector.service import DatabaseConnectionService
from backend.core.deps import get_db, get_current_user
from backend.core.exceptions import NotFoundError, SecurityError
from backend.persistencia.models.user import User

router = APIRouter(prefix="/database", tags=["database-connector"])

SUPPORTED_TYPES = [
    SupportedDbType(
        slug="postgresql", name="PostgreSQL", default_port=5432, icon_hint="elephant"
    ),
    SupportedDbType(
        slug="mysql", name="MySQL", default_port=3306, icon_hint="dolphin"
    ),
]


@router.get("/supported-types", response_model=list[SupportedDbType])
async def get_supported_types():
    return SUPPORTED_TYPES


@router.get("/connections", response_model=list[DatabaseConnectionOut])
async def list_connections(
    context: str | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DatabaseConnectionService(session)
    return await service.list_connections(current_user.id, context)


@router.post("/connections", response_model=DatabaseConnectionOut, status_code=201)
async def create_connection(
    data: DatabaseConnectionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DatabaseConnectionService(session)
    return await service.create_connection(current_user.id, data)


@router.get("/connections/{connection_id}", response_model=DatabaseConnectionOut)
async def get_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DatabaseConnectionService(session)
    try:
        return await service.get_connection(connection_id, current_user.id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.patch("/connections/{connection_id}", response_model=DatabaseConnectionOut)
async def update_connection(
    connection_id: str,
    data: DatabaseConnectionUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DatabaseConnectionService(session)
    try:
        return await service.update_connection(connection_id, current_user.id, data)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DatabaseConnectionService(session)
    try:
        await service.delete_connection(connection_id, current_user.id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.post("/connections/{connection_id}/test", response_model=DatabaseConnectionOut)
async def test_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DatabaseConnectionService(session)
    try:
        return await service.test_connection(connection_id, current_user.id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.post(
    "/connections/{connection_id}/discover-schema",
    response_model=SchemaDiscoveryResult,
)
async def discover_schema(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DatabaseConnectionService(session)
    try:
        return await service.discover_schema(connection_id, current_user.id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.get("/connections/{connection_id}/schema", response_model=SchemaDiscoveryResult)
async def get_schema(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DatabaseConnectionService(session)
    try:
        conn = await service.get_connection(connection_id, current_user.id)
        if not conn.discovered_schema:
            return SchemaDiscoveryResult(tables=[])
        return SchemaDiscoveryResult(**conn.discovered_schema)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.patch("/connections/{connection_id}/schema/enrich")
async def enrich_schema(
    connection_id: str,
    data: SchemaEnrichment,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DatabaseConnectionService(session)
    try:
        return await service.enrich_schema(connection_id, current_user.id, data)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")


@router.post("/connections/{connection_id}/query", response_model=QueryResult)
async def execute_query(
    connection_id: str,
    data: QueryRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DatabaseConnectionService(session)
    try:
        return await service.execute_query(connection_id, current_user.id, data.sql)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Connection not found")
    except SecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
