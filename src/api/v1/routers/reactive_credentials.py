"""Reactive Credentials router — CRUD for encrypted agent secrets."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_db, get_current_user
from src.persistencia.models.user import User
from src.services.credential_service import CredentialService

router = APIRouter(prefix="/reactive/credentials", tags=["reactive-credentials"])


# ── Schemas ──

class CredentialCreate(BaseModel):
    name: str = Field(..., max_length=100)
    key_identifier: str = Field(..., max_length=100)
    value: str = Field(..., min_length=1)
    description: str | None = None


class CredentialOut(BaseModel):
    id: int
    name: str
    key_identifier: str
    description: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ── Endpoints ──

@router.get("", response_model=list[CredentialOut])
async def list_credentials(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all credentials for the current user (values are never returned)."""
    service = CredentialService(session)
    creds = await service.list_for_user(current_user.id)
    return [
        CredentialOut(
            id=c.id,
            name=c.name,
            key_identifier=c.key_identifier,
            description=c.description,
            created_at=c.created_at.isoformat() if c.created_at else "",
            updated_at=c.updated_at.isoformat() if c.updated_at else "",
        )
        for c in creds
    ]


@router.post("", response_model=CredentialOut, status_code=201)
async def create_credential(
    data: CredentialCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Create a new encrypted credential."""
    service = CredentialService(session)
    try:
        cred = await service.create(
            user_id=current_user.id,
            name=data.name,
            key_identifier=data.key_identifier,
            plain_value=data.value,
            description=data.description,
        )
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail=f"A credential with key '{data.key_identifier}' already exists.",
            )
        raise
    return CredentialOut(
        id=cred.id,
        name=cred.name,
        key_identifier=cred.key_identifier,
        description=cred.description,
        created_at=cred.created_at.isoformat() if cred.created_at else "",
        updated_at=cred.updated_at.isoformat() if cred.updated_at else "",
    )


@router.delete("/{cred_id}", status_code=204)
async def delete_credential(
    cred_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Delete a credential. The encrypted value is permanently destroyed."""
    service = CredentialService(session)
    deleted = await service.delete(cred_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential not found")
    return None
