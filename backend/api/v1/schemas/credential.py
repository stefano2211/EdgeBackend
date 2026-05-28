"""Credential schemas — shared between reactive and future chat credential routers."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
