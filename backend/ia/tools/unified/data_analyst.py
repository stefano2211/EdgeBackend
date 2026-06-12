"""Data Analyst tools — LangChain StructuredTools for the data-analyst-agent.

Provides tools that let the DeepAgents subagent:
  1. List available database connections
  2. Retrieve relevant schema items via semantic RAG
  3. Execute natural-language-to-SQL queries with auto-correction
  4. Explain query results in business terms

All tools are async (coroutine=) and accept user_id + context implicitly
via closure binding at creation time.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from backend.core.logging import logging
from backend.ia.tools.unified._session import get_session
from backend.services.data_analyst_service import DataAnalystService
from backend.services.data_analyst_schemas import AnalystQuestion
from backend.services.schema_embedding_service import SchemaEmbeddingService

logger = logging.getLogger(__name__)


def create_data_analyst_tools(user_id: int, context: str = "chat", db_connection_ids: list[str] | None = None) -> list[StructuredTool]:
    """Create all data-analyst tools bound to a specific user and context.

    Args:
        user_id: The authenticated user whose DB connections will be queried.
        context: "chat" or "reactive" — filters which connections are available.

    Returns:
        List of StructuredTool instances ready for DeepAgents registration.
    """

    # ── Tool 1: List available DB connections ─────────────────────────

    async def _list_connections() -> str:
        """List database connections available to the user in this context."""
        async with get_session() as session:
            service = DataAnalystService(session)
            connections = await service._get_available_connections(user_id, context)
            if db_connection_ids:
                connections = [c for c in connections if c.id in db_connection_ids]
            if not connections:
                return "No hay bases de datos conectadas disponibles."
            lines = ["Bases de datos disponibles:"]
            for c in connections:
                lines.append(
                    f"- {c.name} ({c.db_type}) — {c.description or 'Sin descripción'}"
                )
            return "\n".join(lines)

    tool_list_connections = StructuredTool.from_function(
        coroutine=_list_connections,
        name="list_db_connections",
        description=(
            "Lista las bases de datos conectadas disponibles para el usuario. "
            "Usa esto PRIMERO para saber qué bases de datos existen antes de hacer preguntas."
        ),
    )

    # ── Tool 2: Retrieve relevant schema ────────────────────────────────

    async def _retrieve_schema(question: str) -> str:
        """Search for schema items (tables/columns) relevant to a question."""
        async with get_session() as session:
            service = DataAnalystService(session)
            connections = await service._get_available_connections(user_id, context)
            if db_connection_ids:
                connections = [c for c in connections if c.id in db_connection_ids]
            if not connections:
                return "No hay bases de datos disponibles."
            conn_ids = [c.id for c in connections]
            items = await service._retrieve_relevant_schema(
                user_id=user_id,
                question=question,
                connection_ids=conn_ids,
                top_k=15,
            )
            if not items:
                return "No se encontraron tablas o columnas relevantes."

            lines = [f"Schema relevante para: '{question}'"]
            current_table = ""
            for item in items:
                if item.table_name != current_table:
                    current_table = item.table_name
                    desc = f" ({item.description})" if item.description else ""
                    lines.append(f"\nTabla: {item.table_name}{desc}")
                col_line = f"  - {item.column_name} ({item.data_type})"
                if item.is_pk:
                    col_line += " [PK]"
                if item.fk_to:
                    col_line += f" [FK→{item.fk_to}]"
                if item.description:
                    col_line += f" — {item.description}"
                lines.append(col_line)
            return "\n".join(lines)

    tool_retrieve_schema = StructuredTool.from_function(
        coroutine=_retrieve_schema,
        name="retrieve_relevant_schema",
        description=(
            "Busca tablas y columnas relevantes para una pregunta usando búsqueda semántica. "
            "Usa esto DESPUÉS de listar conexiones y ANTES de generar SQL. "
            "Devuelve solo las tablas/columnas más pertinentes, no todo el schema."
        ),
    )

    # ── Tool 3: Execute NL data query ─────────────────────────────────────

    async def _execute_query(question: str, connection_hint: str | None = None) -> str:
        """Execute a natural-language question against the database.

        This tool handles the full pipeline:
        1. Discovers relevant schema via RAG
        2. Generates SQL
        3. Executes with auto-correction (max 3 retries)
        4. Interprets results and returns insights
        """
        async with get_session() as session:
            service = DataAnalystService(session)
            result = await service.ask(
                AnalystQuestion(
                    question=question,
                    connection_hint=connection_hint,
                    context=context,
                    connection_ids=db_connection_ids,
                ),
                user_id=user_id,
            )

            if result.status == "failed":
                return f"Error: {result.error}"

            lines = [
                f"## Respuesta a: {result.question}",
                "",
                f"**Base de datos usada:** {result.connection_used}",
                "",
                "### SQL generada:",
                f"```sql\n{result.sql}\n```",
                "",
            ]

            if result.sql_explanation:
                lines.extend(["**Explicación:**", result.sql_explanation, ""])

            if result.results:
                lines.extend([
                    "### Resultados:",
                    f"Filas: {result.results.row_count}"
                    + (" (truncados)" if result.results.truncated else ""),
                    "",
                ])
                if result.results.columns and result.results.rows:
                    header = " | ".join(result.results.columns)
                    lines.append(header)
                    lines.append(" | ".join(["---"] * len(result.results.columns)))
                    for row in result.results.rows[:20]:
                        lines.append(" | ".join(str(c) for c in row))
                    if result.results.row_count > 20:
                        lines.append(f"... y {result.results.row_count - 20} filas más")
                lines.append("")

            if result.insights:
                lines.extend(["### Insights:", result.insights, ""])

            if result.retries > 0:
                lines.append(f"*(La consulta fue corregida automáticamente tras {result.retries} intento(s))")

            lines.append(f"*Tiempo de ejecución: {result.execution_time_ms}ms*")
            return "\n".join(lines)

    tool_execute_query = StructuredTool.from_function(
        coroutine=_execute_query,
        name="execute_data_query",
        description=(
            "Ejecuta una pregunta en lenguaje natural contra las bases de datos conectadas. "
            "Este es el tool PRINCIPAL del data-analyst-agent. "
            "Recibe una pregunta en español, genera SQL automáticamente, la ejecuta con "
            "corrección automática de errores, e interpreta los resultados. "
            "Opcionalmente acepta un hint del nombre de la conexión a usar."
        ),
    )

    # ── Tool 4: Explain SQL ───────────────────────────────────────────────

    async def _explain_sql(sql: str, connection_hint: str | None = None) -> str:
        """Explain what a SQL query does in plain Spanish."""
        async with get_session() as session:
            service = DataAnalystService(session)
            # Resolve connection_id from hint
            conn_id = None
            if connection_hint:
                conns = await service._get_available_connections(user_id, context)
                if db_connection_ids:
                    conns = [c for c in conns if c.id in db_connection_ids]
                match = next(
                    (c for c in conns if connection_hint.lower() in c.name.lower()),
                    None,
                )
                if match:
                    conn_id = match.id
            explanation = await service.explain_sql(sql, conn_id or "", user_id)
            return explanation

    tool_explain_sql = StructuredTool.from_function(
        coroutine=_explain_sql,
        name="explain_sql_query",
        description=(
            "Explica una consulta SQL en lenguaje natural español. "
            "Útil cuando el usuario quiere entender qué hace una query antes de ejecutarla."
        ),
    )

    return [
        tool_list_connections,
        tool_retrieve_schema,
        tool_execute_query,
        tool_explain_sql,
    ]
