from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class SupportedDbType(BaseModel):
    slug: str
    name: str
    default_port: int
    icon_hint: str

class DatabaseConnectionCreate(BaseModel):
    name: str
    db_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    schema_name: Optional[str] = "public"
    is_readonly: Optional[bool] = True
    max_rows: Optional[int] = 1000
    query_timeout: Optional[int] = 30
    available_in_chat: Optional[bool] = True
    available_in_reactive: Optional[bool] = False

class DatabaseConnectionUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    schema_name: Optional[str] = None
    is_readonly: Optional[bool] = None
    max_rows: Optional[int] = None
    query_timeout: Optional[int] = None
    available_in_chat: Optional[bool] = None
    available_in_reactive: Optional[bool] = None

class DatabaseConnectionOut(BaseModel):
    id: int
    user_id: int
    name: str
    db_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    schema_name: Optional[str] = None
    is_readonly: bool
    max_rows: int
    query_timeout: int
    available_in_chat: bool
    available_in_reactive: bool
    discovered_schema: Optional[dict] = None
    last_schema_sync: Optional[datetime] = None
    status: str
    status_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ColumnDiscovery(BaseModel):
    name: str
    type: str
    nullable: bool
    is_pk: bool
    fk_ref: Optional[str] = None
    description: Optional[str] = None

class TableDiscovery(BaseModel):
    name: str
    description: Optional[str] = None
    row_count: Optional[int] = None
    columns: List[ColumnDiscovery]

class SchemaDiscoveryResult(BaseModel):
    tables: List[TableDiscovery]

class ColumnEnrichment(BaseModel):
    name: str
    description: str

class TableEnrichment(BaseModel):
    name: str
    description: Optional[str] = None
    columns: List[ColumnEnrichment] = []

class SchemaEnrichment(BaseModel):
    tables: List[TableEnrichment]

class QueryRequest(BaseModel):
    sql: str
    params: Optional[Dict[str, Any]] = None

class QueryResult(BaseModel):
    columns: List[str]
    rows: List[Any]
    row_count: int
    truncated: bool
    execution_time_ms: int
