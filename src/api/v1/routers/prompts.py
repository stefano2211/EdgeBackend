"""Prompts router — stub (Fase 7)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("")
async def list_prompts():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Prompt endpoints will be implemented in Fase 7",
    )


@router.post("")
async def create_prompt():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Prompt endpoints will be implemented in Fase 7",
    )


@router.patch("/{prompt_id}")
async def update_prompt(prompt_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Prompt endpoints will be implemented in Fase 7",
    )


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Prompt endpoints will be implemented in Fase 7",
    )
