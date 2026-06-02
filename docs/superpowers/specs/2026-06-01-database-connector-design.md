# Database Connector — Design Specification

> **Date:** 2026-06-01
> **Status:** Approved
> **Scope:** v1 — PostgreSQL + MySQL support with NL2SQL via `db-agent`

---

## 1. Goal

Allow users to connect external SQL databases to the platform. The system auto-discovers the schema and exposes query tools to the AI. Users interact with their data via **natural language (NL2SQL)** — never writing SQL directly.

---

## 2. User Flow

### Phase 1: Connect
1. User clicks "Nueva Conexion" in the Bases de Datos section
2. Selects DB type (PostgreSQL or MySQL)
3. Fills host, port, database, user, password
4. Toggles: readonly, available_in_chat, available_in_reactive, max_rows
5. Clicks "Probar y Guardar"
6. System tests connectivity, then optionally discovers schema

### Phase 2: Use in Chat (NL2SQL)
1. User asks: "Top 5 productos mas vendidos"
2. Orchestrator routes to `db-agent`
3. `db-agent` uses `db_schema` tool to inspect available tables
4. Generates dialect-aware SQL
5. Executes via `db_query` tool (sandboxed)
6. Returns results formatted in markdown tables

### Phase 3: Enrich Schema (Optional)
1. User opens schema viewer
2. Clicks on table/column description field
3. Adds human-readable description
4. Improves future NL2SQL accuracy

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Vue 3)                                           │
│  ├── DashboardLayout.vue (nav item: Bases de Datos)         │
│  ├── DatabaseLayout.vue (tab layout)                        │
│  ├── DatabaseConnectionsView.vue (grid + cards)             │
│  ├── DatabaseConnectionModal.vue (form + test)              │
│  └── DatabaseSchemaViewer.vue (tree + enrichment)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend API (FastAPI)                                     │
│  ├── /api/v1/database/connections (CRUD)                     │
│  ├── /api/v1/database/connections/{id}/test                │
│  ├── /api/v1/database/connections/{id}/discover-schema    │
│  ├── /api/v1/database/connections/{id}/schema               │
│  ├── /api/v1/database/connections/{id}/schema/enrich       │
│  └── /api/v1/database/connections/{id}/query (admin)       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Service Layer                                              │
│  ├── DatabaseConnectionService                              │
│  │   ├── create/test/delete connections                     │
│  │   ├── discover_schema (introspection)                     │
│  │   ├── execute_query (sandboxed)                          │
│  │   └── build_schema_context (for AI prompts)             │
│  ├── EngineFactory (async engines, cached)                  │
│  └── CredentialVault integration (AES-256-GCM)             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  AI Pipeline                                                │
│  ├── db-agent (new subagent)                                │
│  │   ├── db_query tool (sandboxed execution)                │
│  │   ├── db_schema tool (introspection)                    │
│  │   └── self-correction loop (max 3 retries)               │
│  ├── Orchestrator routing rules (proactive + reactive)    │
│  └── Schema context injection into prompts                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Backend Components

### 4.1 Models

**`DatabaseConnection`** (`backend/database_connector/models.py`)

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID | FK -> users |
| `name` | String(255) | Display name |
| `db_type` | Enum | `postgresql`, `mysql` |
| `host` | String(255) | Hostname/IP |
| `port` | Integer | Port |
| `database_name` | String(255) | DB name |
| `schema_name` | String(255) | Default: `public` (PG) / null (MySQL) |
| `is_readonly` | Boolean | Default `True` |
| `max_rows` | Integer | Default `1000` |
| `query_timeout` | Integer | Default `30` (seconds) |
| `available_in_chat` | Boolean | Default `True` |
| `available_in_reactive` | Boolean | Default `False` |
| `discovered_schema` | JSON | Cached schema: `{tables: [{name, description, row_count?, columns: [{name, type, nullable, is_pk, fk_ref?, description}]}]}` |
| `last_schema_sync` | DateTime | Last discovery timestamp |
| `status` | Enum | `connected`, `disconnected`, `error` |
| `status_message` | Text | Error details |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

**`DbConnectionCredential`** (`backend/database_connector/credential_model.py`)

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | PK |
| `connection_id` | UUID | FK -> database_connections |
| `username` | LargeBinary | AES-256-GCM encrypted |
| `password` | LargeBinary | AES-256-GCM encrypted |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

Uses `CredentialVault` (same as integration credentials) — AES-256-GCM with PBKDF2-HMAC-SHA256 key derivation. No plaintext ever stored.

### 4.2 Engine Factory

```python
DRIVERS = {
    "postgresql": "postgresql+asyncpg",
    "mysql": "mysql+aiomysql",
}
```

- Engines cached per `connection_id` with TTL (30 min)
- `get_engine(connection_id)` -> `AsyncEngine`
- `dispose_engine(connection_id)` -> cleanup on delete
- Credentials decrypted in-memory only at engine creation time
- Connection pooling via SQLAlchemy async

### 4.3 Security (Defense in Depth)

Following industrial standards (Airbyte, Metabase, LangChain):

**Layer 1 — DB Permissions (documented recommendation):**
- Document that users should create a dedicated read-only DB user
- `GRANT USAGE ON SCHEMA public TO aura_readonly;`
- `GRANT SELECT ON ALL TABLES IN SCHEMA public TO aura_readonly;`

**Layer 2 — SQLFluff Parse-Time Validation:**
```python
from sqlfluff.core import Linter

linter = Linter(dialect="postgres")  # or "mysql"
parsed = linter.parse_string(sql)
for violation in parsed.violations:
    if violation.rule_code() in ("AL02", "AL03", ...):  # DDL rules
        raise SecurityError("DDL/DML not allowed")
```

**Layer 3 — Regex Backup:**
```python
BLOCKED_PATTERNS = re.compile(
    r'\b(DROP|ALTER|TRUNCATE|CREATE|INSERT|UPDATE|DELETE|GRANT|REVOKE)\b',
    re.IGNORECASE
)
```

**Layer 4 — Transaction-Level Read-Only:**
```python
if connection.is_readonly:
    await conn.execute(text("SET TRANSACTION READ ONLY"))
```

**Layer 5 — Runtime Limits:**
```python
result = await asyncio.wait_for(
    conn.execute(text(sql)),
    timeout=connection.query_timeout
)
rows = result.fetchmany(connection.max_rows)
```

### 4.4 AI Tools

**`db_query` tool** (`backend/ia/tools/unified/db.py`)

```python
Signature: (connection_name: str, sql_query: str)

Returns: {
    "columns": ["name", "qty"],
    "rows": [["Product A", 150], ...],
    "row_count": 5,
    "truncated": False,
    "execution_time_ms": 42
}

Self-correction:
- If query fails, error returned to agent
- Agent may retry with corrected SQL
- Max 3 attempts per invocation
```

**`db_schema` tool** (`backend/ia/tools/unified/db.py`)

```python
Signature: (connection_name: str | None = None)

Returns: SchemaDiscoveryResult for specified connection,
         or all connections if connection_name is None.
         Includes user-provided descriptions.
```

### 4.5 Subagent Registration

**`db-agent`** (`backend/ia/subagents/builders.py`)

```python
SubagentRegistry.register(SubagentPlugin(
    name="db",
    description="Database query specialist...",
    builder=_build_db_subagent,
    applies_to={"proactive", "reactive"},
    requires_rag=False,
    requires_mcp=False,
))
```

**Orchestrator routing rules** (`backend/ia/prompts/orchestrator.py`):
```
[IF] User asks about data, tables, metrics, analytics, or anything
     related to their connected databases
     -> [DELEGATE] to db-agent via task()
```

---

## 5. Frontend Components

### 5.1 Navigation

**`DashboardLayout.vue`** — new nav item:
```typescript
{
    label: 'Bases de Datos',
    path: '/database',
    icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7...' // cylinder SVG
}
```
Color: `cyan-400/500` accent.

### 5.2 Views

**`DatabaseConnectionsView.vue`**:
- Header: "Bases de Datos" + "Nueva Conexion" button (cyan)
- Grid of cards per connection:
  - DB type icon (PostgreSQL elephant, MySQL dolphin)
  - Name, host:port/database
  - Status badge (green/yellow/red dot + text)
  - Table count from `discovered_schema`
  - Tags: "Chat", "Reactiva"
  - Actions: Test, Sync Schema, Editar, Eliminar
- Empty state: illustration + "Conecta tu primera base de datos" + CTA

**`DatabaseConnectionModal.vue`**:
Single-page form (not wizard — only 2 DB types):
- Section 1: Tipo de DB (radio cards with icons)
- Section 2: Conexion (host, port, database, user, password)
- Section 3: Opciones (toggles: readonly, chat, reactive, max_rows input)
- Bottom: "Probar y Guardar" button
  - On click: test -> if success, save + optional "Descubrir Schema" checkbox

**`DatabaseSchemaViewer.vue`**:
- Expandable tree:
  - Level 1: Database name (icon: database)
  - Level 2: Table (icon: table) + row count badge + editable description
  - Level 3: Column (icon by type) + type + PK/FK badges + editable description
- Editable descriptions trigger `PATCH /schema/enrich` on blur

### 5.3 Service

**`frontend/src/services/databaseService.ts`**:
```typescript
export const databaseService = {
    getSupportedTypes: () => api.get('/api/v1/database/supported-types'),
    listConnections: () => api.get('/api/v1/database/connections'),
    createConnection: (data) => api.post('/api/v1/database/connections', data),
    getConnection: (id) => api.get(`/api/v1/database/connections/${id}`),
    updateConnection: (id, data) => api.patch(`/api/v1/database/connections/${id}`, data),
    deleteConnection: (id) => api.delete(`/api/v1/database/connections/${id}`),
    testConnection: (id) => api.post(`/api/v1/database/connections/${id}/test`),
    discoverSchema: (id) => api.post(`/api/v1/database/connections/${id}/discover-schema`),
    getSchema: (id) => api.get(`/api/v1/database/connections/${id}/schema`),
    enrichSchema: (id, data) => api.patch(`/api/v1/database/connections/${id}/schema/enrich`, data),
    executeQuery: (id, sql) => api.post(`/api/v1/database/connections/${id}/query`, { sql }),
}
```

---

## 6. API Routes

Prefix: `/api/v1/database`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/supported-types` | List PG + MySQL with metadata | User |
| POST | `/connections` | Create connection | User |
| GET | `/connections` | List user's connections | User |
| GET | `/connections/{id}` | Get connection detail | User |
| PATCH | `/connections/{id}` | Update connection | User |
| DELETE | `/connections/{id}` | Delete + cleanup | User |
| POST | `/connections/{id}/test` | Test connectivity | User |
| POST | `/connections/{id}/discover-schema` | Run introspection | User |
| GET | `/connections/{id}/schema` | Get cached schema | User |
| PATCH | `/connections/{id}/schema/enrich` | Update descriptions | User |
| POST | `/connections/{id}/query` | Manual SQL execution | Admin* |

*Admin-only for manual query endpoint.

---

## 7. Dependencies

Add to `pyproject.toml`:
```toml
"aiomysql>=0.2.0",
"sqlfluff>=3.0.0",
```

`asyncpg` already present.

---

## 8. Files Changed / Created

### New Files (Backend)
| File | Responsibility |
|------|--------------|
| `backend/database_connector/__init__.py` | Package init |
| `backend/database_connector/models.py` | `DatabaseConnection` model |
| `backend/database_connector/credential_model.py` | `DbConnectionCredential` model |
| `backend/database_connector/schemas.py` | Pydantic schemas |
| `backend/database_connector/repository.py` | Repository |
| `backend/database_connector/service.py` | Business logic |
| `backend/database_connector/engine_factory.py` | Async engine factory |
| `backend/database_connector/routers.py` | FastAPI routes |
| `backend/ia/tools/unified/db.py` | `db_query`, `db_schema` tools |
| `backend/ia/prompts/templates/subagent_db.md` | System prompt template |

### Modified Files (Backend)
| File | Change |
|------|--------|
| `backend/ia/subagents/builders.py` | Add `_build_db_subagent` + registration |
| `backend/ia/prompts/subagents.py` | Add `DB_AGENT_DESCRIPTION`, `build_db_system_prompt` |
| `backend/ia/prompts/__init__.py` | Export DB symbols |
| `backend/ia/prompts/orchestrator.py` | Add db-agent routing rules |
| `backend/ia/prompts/reactive.py` | Add db-agent to reactive orchestrator |
| `backend/ia/orchestrator_factory.py` | Add "db" to default subagent names |
| `backend/ia/tools/unified/__init__.py` | Export db tools |
| `backend/api/v1/router.py` | Include database router |
| `backend/persistencia/models/__init__.py` | Register new models |
| `pyproject.toml` | Add `aiomysql`, `sqlfluff` |

### New Files (Frontend)
| File | Responsibility |
|------|--------------|
| `frontend/src/views/database/DatabaseLayout.vue` | Tab layout |
| `frontend/src/views/database/DatabaseConnectionsView.vue` | Connection grid |
| `frontend/src/views/database/DatabaseConnectionModal.vue` | Connection form |
| `frontend/src/views/database/DatabaseSchemaViewer.vue` | Schema tree |
| `frontend/src/services/databaseService.ts` | API client |

### Modified Files (Frontend)
| File | Change |
|------|--------|
| `frontend/src/router/index.ts` | Add `/database` routes |
| `frontend/src/layouts/DashboardLayout.vue` | Add nav item |

---

## 9. Verification Plan

### Automated Tests
```bash
pytest tests/test_database_connector.py -v
pytest tests/test_database_connector_integration.py -v
```

Tests cover:
- CRUD of connections
- Encryption/decryption of credentials
- Test connectivity to local Postgres (Docker Compose)
- Schema discovery (EdgeBackend's own tables)
- Schema enrichment
- Query execution with read-only enforcement
- DDL blocking (attempt `DROP TABLE` -> error)
- Timeout enforcement
- Row limit enforcement
- SQLFluff validation

### Manual Verification
1. `docker compose up -d postgres`
2. `uvicorn backend.main:app --reload`
3. Frontend: nav item "Bases de Datos" visible with cyan accent
4. Create connection to local Postgres
5. Test -> success
6. Discover schema -> tree viewer shows EdgeBackend tables
7. Enrich: add description to `users` table
8. Chat: "Cuantos usuarios hay?" -> db-agent generates SQL -> result
9. Chat: "Muéstrame las ultimas 5 conversaciones" -> table markdown output

---

## 10. Out of Scope (v2)

- SQLite, MSSQL support
- SSH tunneling
- SSL mode configuration (require/verify-ca/verify-full)
- Connection pooling metrics / monitoring
- Query caching beyond schema cache
- Row-level security / permission per table
- Query history / audit log per query
- Data visualization (charts from query results)

---

## 11. Open Questions Resolved

| Question | Decision |
|----------|----------|
| DBs soportadas v1 | PostgreSQL + MySQL (open source) |
| Modelo de interacción | NL2SQL primario en chat + endpoint manual para admin/testing |
| Schema enrichment | Si, descripciones editables en tablas/columnas |
| Color accent | Cyan (`cyan-400/500`) |
| Formulario vs wizard | Formulario de 1 pagina (solo 2 DB types) |
| Seguridad DDL | SQLFluff parseado + regex + read-only transaction + timeout |

---

## 12. Industrial Standards Applied

| Practice | Source | Implementation |
|----------|--------|----------------|
| Read-only users | Airbyte | Documented recommendation + `is_readonly` flag |
| SSL modes | Airbyte | Documented (v2: configurable) |
| SQL parse validation | SQLFluff | Layer 2 defense before execution |
| Schema introspection | Airbyte | `information_schema` / `pg_catalog` |
| NL2SQL self-correction | Vanna AI | Max 3 retries with error feedback |
| Schema enrichment | Metabase semantic layer | Descriptions improve NL2SQL |
| Tool-based execution | LangChain | StructuredTool, never direct DB access |
| Row limits | LangChain | `fetchmany(max_rows)` |

---

*End of specification.*
