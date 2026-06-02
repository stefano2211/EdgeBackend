from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class SupportedDbType(BaseModel):
    slug: str
    name: str
    default_port: int
    icon_hint: str


class DatabaseConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    db_type: str = Field(..., pattern="^(postgresql|mysql)$")
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., gt=0, le=65535)
    database_name: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)
    schema_name: str | None = Field(default=None, max_length=255)
    is_readonly: bool = True
    max_rows: int = Field(default=1000, ge=1, le=10000)
    query_timeout: int = Field(default=30, ge=1, le=300)
    available_in_chat: bool = True
    available_in_reactive: bool = False


class DatabaseConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, gt=0, le=65535)
    database_name: str | None = Field(default=None, max_length=255)
    schema_name: str | None = Field(default=None, max_length=255)
    is_readonly: bool | None = None
    max_rows: int | None = Field(default=None, ge=1, le=10000)
    query_timeout: int | None = Field(default=None, ge=1, le=300)
    available_in_chat: bool | None = None
    available_in_reactive: bool | None = None


class DatabaseConnectionOut(BaseModel):
    id: str
    name: str
    db_type: str
    host: str
    port: int
    database_name: str
    schema_name: str | None
    is_readonly: bool
    max_rows: int
    query_timeout: int
    available_in_chat: bool
    available_in_reactive: bool
    discovered_schema: dict | None
    last_schema_sync: datetime | None
    status: str
    status_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SchemaColumn(BaseModel):
    name: str
    type: str
    nullable: bool
    is_pk: bool = False
    fk_ref: str | None = None
    description: str | None = None


class SchemaTable(BaseModel):
    name: str
    description: str | None = None
    row_count: int | None = None
    columns: list[SchemaColumn]


class SchemaDiscoveryResult(BaseModel):
    tables: list[SchemaTable]


class SchemaEnrichment(BaseModel):
    tables: list[SchemaTable]


class QueryRequest(BaseModel):
    sql: str = Field(..., min_length=1)


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool
    execution_time_ms: int
