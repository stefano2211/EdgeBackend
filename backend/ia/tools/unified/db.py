from __future__ import annotations

from langchain_core.tools import StructuredTool

from backend.database_connector.service import DatabaseConnectionService
from backend.database_connector.schemas import QueryResult
from backend.ia.tools.unified._session import get_session


def create_db_query_tool(user_id: int, context: str = "chat") -> StructuredTool:
    async def _db_query(connection_name: str, sql_query: str) -> str:
        """Execute a SQL query against a connected database. Returns results as markdown table."""
        async with get_session() as session:
            service = DatabaseConnectionService(session)
            # Find connection by name for this user
            conns = await service.list_connections(user_id, context)
            conn = next((c for c in conns if c.name == connection_name), None)
            if not conn:
                return f"Error: No connection named '{connection_name}' found."

            result: QueryResult = await service.execute_query(
                conn.id, user_id, sql_query
            )

            if result.row_count == 0:
                return "Query executed successfully. No rows returned."

            # Format as markdown table
            lines = []
            lines.append("| " + " | ".join(result.columns) + " |")
            lines.append("| " + " | ".join(["---"] * len(result.columns)) + " |")
            for row in result.rows:
                lines.append("| " + " | ".join(str(c) for c in row) + " |")

            if result.truncated:
                lines.append(
                    f"\n*Results truncated to {result.row_count} rows. "
                    f"Execution time: {result.execution_time_ms}ms*"
                )
            else:
                lines.append(
                    f"\n*{result.row_count} rows returned. "
                    f"Execution time: {result.execution_time_ms}ms*"
                )

            return "\n".join(lines)

    return StructuredTool.from_function(
        coroutine=_db_query,
        name="db_query",
        description=(
            "Execute a SQL SELECT query against a connected database. "
            "Use ONLY after inspecting the schema with db_schema. "
            "The query must be read-only. "
            "If the query fails, you will receive the error and can retry with corrected SQL (max 3 attempts)."
        ),
    )


def create_db_schema_tool(user_id: int, context: str = "chat") -> StructuredTool:
    async def _db_schema(connection_name: str | None = None) -> str:
        """Get the schema of a connected database. If no name provided, returns all schemas."""
        async with get_session() as session:
            service = DatabaseConnectionService(session)
            conns = await service.list_connections(user_id, context)

            if connection_name:
                conn = next((c for c in conns if c.name == connection_name), None)
                if not conn:
                    return f"Error: No connection named '{connection_name}' found."
                ctx = await service.build_schema_context(conn.id, user_id)
                return ctx
            else:
                return await service.build_schema_context_all(user_id, context)

    return StructuredTool.from_function(
        coroutine=_db_schema,
        name="db_schema",
        description=(
            "Get the database schema for one or all connected databases. "
            "Use this BEFORE generating SQL to understand available tables, columns, types, and relationships. "
            "Returns a text summary with table names, column names, types, and any user-provided descriptions."
        ),
    )
