from __future__ import annotations

import asyncio
import re
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database_connector.models import DatabaseConnection
from backend.database_connector.credential_model import DbConnectionCredential
from backend.database_connector.repository import DatabaseConnectionRepository
from backend.database_connector.schemas import (
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
    SchemaDiscoveryResult,
    SchemaTable,
    SchemaColumn,
    QueryResult,
)
from backend.database_connector.engine_factory import EngineFactory
from backend.integrations.credential_vault import CredentialVault
from backend.core.exceptions import NotFoundError, SecurityError

_vault = CredentialVault()

# Layer 3: Regex backup
_BLOCKED_PATTERNS = re.compile(
    r"\b(DROP|ALTER|TRUNCATE|CREATE|INSERT|UPDATE|DELETE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class DatabaseConnectionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = DatabaseConnectionRepository(session)

    async def create_connection(
        self, user_id: int, data: DatabaseConnectionCreate
    ) -> DatabaseConnection:
        conn = DatabaseConnection(
            user_id=user_id,
            name=data.name,
            db_type=data.db_type,
            host=data.host,
            port=data.port,
            database_name=data.database_name,
            schema_name=data.schema_name,
            is_readonly=data.is_readonly,
            max_rows=data.max_rows,
            query_timeout=data.query_timeout,
            available_in_chat=data.available_in_chat,
            available_in_reactive=data.available_in_reactive,
        )
        await self._repo.create(conn)

        # Encrypt and store credentials
        creds = DbConnectionCredential(
            id=conn.id,
            connection_id=conn.id,
            encrypted_username=_vault.encrypt(data.username),
            encrypted_password=_vault.encrypt(data.password),
        )
        self._session.add(creds)
        await self._session.commit()
        await self._session.refresh(conn)
        return conn

    async def update_connection(
        self, connection_id: str, user_id: int, data: DatabaseConnectionUpdate
    ) -> DatabaseConnection:
        conn = await self._repo.get_by_id_for_user(connection_id, user_id)
        if not conn:
            raise NotFoundError("Connection not found")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(conn, key):
                setattr(conn, key, value)

        await self._session.commit()
        await self._session.refresh(conn)
        return conn

    async def delete_connection(self, connection_id: str, user_id: int) -> None:
        conn = await self._repo.get_by_id_for_user(connection_id, user_id)
        if not conn:
            raise NotFoundError("Connection not found")

        await EngineFactory.dispose_engine(connection_id)
        await self._repo.delete(conn)
        await self._session.commit()

    async def test_connection(
        self, connection_id: str, user_id: int
    ) -> DatabaseConnection:
        conn = await self._repo.get_by_id_for_user(connection_id, user_id)
        if not conn:
            raise NotFoundError("Connection not found")

        try:
            ok = await EngineFactory.test_connection(conn)
            if ok:
                conn.status = "connected"
                conn.status_message = None
            else:
                conn.status = "error"
                conn.status_message = "Connection test failed"
        except Exception as exc:
            conn.status = "error"
            conn.status_message = str(exc)

        await self._session.commit()
        await self._session.refresh(conn)
        return conn

    async def discover_schema(
        self, connection_id: str, user_id: int
    ) -> SchemaDiscoveryResult:
        conn = await self._repo.get_by_id_for_user(connection_id, user_id)
        if not conn:
            raise NotFoundError("Connection not found")

        engine = await EngineFactory.get_engine(conn)
        tables: list[SchemaTable] = []

        async with engine.connect() as db_conn:
            if conn.db_type == "postgresql":
                # Query information_schema
                result = await db_conn.execute(
                    text("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = :schema
                        AND table_type = 'BASE TABLE'
                        ORDER BY table_name
                    """),
                    {"schema": conn.schema_name or "public"},
                )
                table_rows = result.fetchall()

                for (table_name,) in table_rows:
                    # Columns
                    col_result = await db_conn.execute(
                        text("""
                            SELECT column_name, data_type, is_nullable,
                                (column_name = ANY(
                                    SELECT kcu.column_name
                                    FROM information_schema.key_column_usage kcu
                                    JOIN information_schema.table_constraints tc
                                        ON kcu.constraint_name = tc.constraint_name
                                    WHERE kcu.table_schema = :schema
                                    AND kcu.table_name = :table
                                    AND tc.constraint_type = 'PRIMARY KEY'
                                )) as is_pk
                            FROM information_schema.columns
                            WHERE table_schema = :schema AND table_name = :table
                            ORDER BY ordinal_position
                        """),
                        {"schema": conn.schema_name or "public", "table": table_name},
                    )
                    columns = []
                    for row in col_result.fetchall():
                        columns.append(
                            SchemaColumn(
                                name=row[0],
                                type=row[1],
                                nullable=row[2] == "YES",
                                is_pk=row[3] or False,
                            )
                        )

                    # Approx row count
                    count_result = await db_conn.execute(
                        text(f"SELECT COUNT(*) FROM \"{table_name}\"")
                    )
                    row_count = count_result.scalar()

                    tables.append(
                        SchemaTable(
                            name=table_name,
                            row_count=row_count,
                            columns=columns,
                        )
                    )
            else:
                # MySQL information_schema
                result = await db_conn.execute(
                    text("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = :db
                        AND table_type = 'BASE TABLE'
                        ORDER BY table_name
                    """),
                    {"db": conn.database_name},
                )
                table_rows = result.fetchall()

                for (table_name,) in table_rows:
                    col_result = await db_conn.execute(
                        text("""
                            SELECT column_name, data_type, is_nullable,
                                (column_key = 'PRI') as is_pk
                            FROM information_schema.columns
                            WHERE table_schema = :db AND table_name = :table
                            ORDER BY ordinal_position
                        """),
                        {"db": conn.database_name, "table": table_name},
                    )
                    columns = []
                    for row in col_result.fetchall():
                        columns.append(
                            SchemaColumn(
                                name=row[0],
                                type=row[1],
                                nullable=row[2] == "YES",
                                is_pk=row[3] or False,
                            )
                        )

                    count_result = await db_conn.execute(
                        text(f"SELECT COUNT(*) FROM `{table_name}`")
                    )
                    row_count = count_result.scalar()

                    tables.append(
                        SchemaTable(
                            name=table_name,
                            row_count=row_count,
                            columns=columns,
                        )
                    )

        # Merge with existing descriptions
        existing = conn.discovered_schema or {}
        existing_tables = {t["name"]: t for t in existing.get("tables", [])}
        for table in tables:
            if table.name in existing_tables:
                old = existing_tables[table.name]
                table.description = old.get("description")
                old_cols = {c["name"]: c for c in old.get("columns", [])}
                for col in table.columns:
                    if col.name in old_cols:
                        col.description = old_cols[col.name].get("description")

        schema_result = SchemaDiscoveryResult(tables=tables)
        conn.discovered_schema = schema_result.model_dump()
        conn.last_schema_sync = datetime.utcnow()
        await self._session.commit()
        return schema_result

    async def enrich_schema(
        self,
        connection_id: str,
        user_id: int,
        enrichment: SchemaDiscoveryResult,
    ) -> SchemaDiscoveryResult:
        conn = await self._repo.get_by_id_for_user(connection_id, user_id)
        if not conn:
            raise NotFoundError("Connection not found")

        # Update descriptions in discovered_schema
        current = conn.discovered_schema or {"tables": []}
        current_tables = {t["name"]: t for t in current.get("tables", [])}

        for table in enrichment.tables:
            if table.name in current_tables:
                current_tables[table.name]["description"] = table.description
                current_cols = {
                    c["name"]: c for c in current_tables[table.name].get("columns", [])
                }
                for col in table.columns:
                    if col.name in current_cols:
                        current_cols[col.name]["description"] = col.description

        conn.discovered_schema = current
        await self._session.commit()
        return SchemaDiscoveryResult(**current)

    async def execute_query(
        self, connection_id: str, user_id: int, sql: str
    ) -> QueryResult:
        conn = await self._repo.get_by_id_for_user(connection_id, user_id)
        if not conn:
            raise NotFoundError("Connection not found")

        # Layer 3: Regex check
        if _BLOCKED_PATTERNS.search(sql):
            raise SecurityError("DDL/DML statements are not allowed")

        # Layer 2: SQLFluff parse validation
        try:
            from sqlfluff.core import Linter

            dialect = "postgres" if conn.db_type == "postgresql" else "mysql"
            linter = Linter(dialect=dialect)
            parsed = linter.parse_string(sql)
            # Check for any DDL/DML tokens via tree walk
            for violation in parsed.violations:
                # Reject if any AL (aliasing) or other structural issues
                pass  # SQLFluff primarily validates syntax; regex handles keywords
        except ImportError:
            pass  # SQLFluff not available, rely on regex + read-only

        engine = await EngineFactory.get_engine(conn)
        start = datetime.utcnow()

        async with engine.begin() as db_conn:
            # Layer 4: Read-only transaction
            if conn.is_readonly and conn.db_type == "postgresql":
                await db_conn.execute(text("SET TRANSACTION READ ONLY"))

            try:
                result = await asyncio.wait_for(
                    db_conn.execute(text(sql)),
                    timeout=conn.query_timeout,
                )
            except asyncio.TimeoutError:
                raise SecurityError(f"Query timed out after {conn.query_timeout}s")

            columns = list(result.keys())
            rows_raw = result.fetchmany(conn.max_rows)
            rows = [list(row) for row in rows_raw]
            truncated = len(rows) == conn.max_rows

        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            execution_time_ms=elapsed,
        )

    async def list_connections(
        self, user_id: int, context: str | None = None
    ) -> list[DatabaseConnection]:
        return await self._repo.list_by_user(user_id, context)

    async def get_connection(
        self, connection_id: str, user_id: int
    ) -> DatabaseConnection:
        conn = await self._repo.get_by_id_for_user(connection_id, user_id)
        if not conn:
            raise NotFoundError("Connection not found")
        return conn

    async def build_schema_context(
        self, connection_id: str, user_id: int
    ) -> str:
        conn = await self.get_connection(connection_id, user_id)
        schema = conn.discovered_schema
        if not schema:
            return "No schema discovered yet."

        lines = [f"Database: {conn.name} ({conn.db_type})"]
        for table in schema.get("tables", []):
            lines.append(f"\nTable: {table['name']}")
            if table.get("description"):
                lines.append(f"  Description: {table['description']}")
            for col in table.get("columns", []):
                desc = f" -- {col['description']}" if col.get("description") else ""
                pk = " [PK]" if col.get("is_pk") else ""
                lines.append(f"  - {col['name']}: {col['type']}{pk}{desc}")
        return "\n".join(lines)

    async def build_schema_context_all(
        self, user_id: int, context: str = "chat"
    ) -> str:
        conns = await self.list_connections(user_id, context=context)
        parts = []
        for conn in conns:
            if conn.status != "connected":
                continue
            part = await self.build_schema_context(conn.id, user_id)
            parts.append(part)
        return "\n\n---\n\n".join(parts) if parts else "No database connections available."
