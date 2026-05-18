"""Domain configuration schemas.

Clean separation between API contract and internal models.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DetectionRules(BaseModel):
    """User-configurable rules for automatic domain detection."""

    keywords: list[str] = Field(default_factory=list)
    source_patterns: list[str] = Field(default_factory=list)
    severity_map: dict[str, str] = Field(default_factory=dict)


class DomainConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    detection_rules: DetectionRules | None = None
    is_default: bool = False


class DomainConfigUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    detection_rules: DetectionRules | None = None
    is_default: bool | None = None
    is_enabled: bool | None = None


class DomainConfigOut(BaseModel):
    id: int
    user_id: int
    name: str
    display_name: str
    detection_rules: dict | None
    is_default: bool
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DomainConfigListResponse(BaseModel):
    items: list[DomainConfigOut]


class DomainDetectTestPayload(BaseModel):
    payload: dict
    source: str | None = None


class DomainDetectTestResponse(BaseModel):
    domain: str
    subdomain: str | None
    confidence: float
    source: str  # rule | llm | llm_cache
