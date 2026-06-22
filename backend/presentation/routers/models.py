"""Models router — functional CRUD + discovery."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.presentation.schemas.model import ModelConfigCreate, ModelConfigOut
from backend.core.deps import get_db, get_current_user
from backend.domain.models.user import User
from backend.application.admin.models import ModelService

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelConfigOut])
async def list_models(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    models = await service.list()
    return models


@router.get("/{model_id}", response_model=ModelConfigOut)
async def get_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    model = await service.get(model_id)
    return model


@router.post("", response_model=ModelConfigOut, status_code=201)
async def create_model(
    data: ModelConfigCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    model = await service.create(data)
    return model


@router.put("/{model_id}", response_model=ModelConfigOut)
async def update_model(
    model_id: int,
    data: ModelConfigCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    model = await service.update(model_id, data)
    return model


@router.delete("/{model_id}", status_code=204)
async def delete_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    await service.delete(model_id)
    return None


@router.get("/discovery/providers")
async def list_providers(
    current_user: User = Depends(get_current_user),
):
    return [{"id": "vllm", "name": "vLLM"}, {"id": "ollama", "name": "Ollama"}]


@router.get("/discovery/models/{provider}")
async def list_provider_models(
    provider: str,
    current_user: User = Depends(get_current_user),
):
    if provider == "vllm":
        return [{"id": "Qwen/Qwen3.5-9B-Instruct", "name": "Qwen 3.5 9B"}]
    if provider == "ollama":
        return [{"id": "qwen3.5:4b", "name": "Qwen 3.5 4B"}]
    return []
