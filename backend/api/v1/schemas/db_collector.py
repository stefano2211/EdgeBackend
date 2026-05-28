from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DbSourceCreate(BaseModel):
    name: str
    db_type: str
    connection_string: str | None = None
    query: str | None = None
    cron_expression: str | None = None


class DbSourceUpdate(BaseModel):
    name: str | None = None
    db_type: str | None = None
    connection_string: str | None = None
    query: str | None = None
    cron_expression: str | None = None
    is_enabled: bool | None = None


class DbSourceOut(BaseModel):
    id: int
    name: str
    db_type: str
    connection_string: str | None = None
    query: str | None = None
    cron_expression: str | None = None
    is_enabled: bool
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
