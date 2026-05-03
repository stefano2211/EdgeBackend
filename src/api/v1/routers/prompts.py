"""Prompts router — functional CRUD."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.prompt import PromptCreate, PromptUpdate, PromptOut
from src.core.database import AsyncSessionLocal
from src.core.deps import get_current_user_id
from src.core.exceptions import NotFoundError
from src.services.prompt_service import PromptService

router = APIRouter(prefix="/prompts", tags=["prompts"])


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@router.get("", response_model=list[PromptOut])
async def list_prompts(
    session: AsyncSession = Depends(get_db),
):
    service = PromptService(session)
    return await service.list_prompts()


@router.post("", response_model=PromptOut, status_code=201)
async def create_prompt(
    data: PromptCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = PromptService(session)
    return await service.create_prompt(data)


@router.patch("/{prompt_id}", response_model=PromptOut)
async def update_prompt(
    prompt_id: int,
    data: PromptUpdate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = PromptService(session)
    return await service.update_prompt(prompt_id, data)


@router.delete("/{prompt_id}", status_code=204)
async def delete_prompt(
    prompt_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = PromptService(session)
    await service.delete_prompt(prompt_id)
