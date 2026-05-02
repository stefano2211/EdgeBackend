"""Models router — functional CRUD + discovery."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.model import ModelConfigCreate, ModelConfigOut
from src.core.database import AsyncSessionLocal
from src.core.deps import get_current_user_id
from src.services.model_service import ModelService

router = APIRouter(prefix="/models", tags=["models"])


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@router.get("", response_model=list[ModelConfigOut])
async def list_models(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    models = await service.list_models()
    return models


@router.get("/{model_id}", response_model=ModelConfigOut)
async def get_model(
    model_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    model = await service.get_model(model_id)
    return model


@router.post("", response_model=ModelConfigOut, status_code=201)
async def create_model(
    data: ModelConfigCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    model = await service.create_model(data)
    return model


@router.put("/{model_id}", response_model=ModelConfigOut)
async def update_model(
    model_id: int,
    data: ModelConfigCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    model = await service.update_model(model_id, data)
    return model


@router.delete("/{model_id}", status_code=204)
async def delete_model(
    model_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    await service.delete_model(model_id)
    return None


@router.get("/discovery/providers")
async def list_providers(
    user_id: int = Depends(get_current_user_id),
):
    return [{"id": "vllm", "name": "vLLM"}, {"id": "ollama", "name": "Ollama"}]


@router.get("/discovery/models/{provider}")
async def list_provider_models(
    provider: str,
    user_id: int = Depends(get_current_user_id),
):
    if provider == "vllm":
        return [{"id": "Qwen/Qwen3.5-9B-Instruct", "name": "Qwen 3.5 9B"}]
    if provider == "ollama":
        return [{"id": "qwen3.5:9b", "name": "Qwen 3.5 9B"}]
    return []
