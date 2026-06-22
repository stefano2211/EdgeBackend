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
from backend.ia.tools.session import get_session
from backend.application.data_analysis.service import DataAnalystService
from backend.application.data_analysis.schemas import AnalystQuestion
from backend.infrastructure.embeddings.schema_embeddings import SchemaEmbeddingService

logger = logging.getLogger(__name__)


def _safe_str(s: str) -> str:
    """Escape single quotes for SQL string literals."""
    return s.replace("'", "''")


def _safe_ident(s: str, dialect: str = "postgresql") -> str:
    """Quote SQL identifiers for the target dialect."""
    if dialect == "mysql":
        return f"`{s}`"
    return f'"{s}"'


def _time_interval_sql(hours: int, time_col: str, dialect: str = "postgresql") -> str:
    """Generate the time interval WHERE clause for the target dialect."""
    if dialect == "mysql":
        return f"{_safe_ident(time_col, dialect)} >= NOW() - INTERVAL {hours} HOUR"
    elif dialect == "sqlite":
        return f"{_safe_ident(time_col, dialect)} >= datetime('now', '-{hours} hours')"
    return f"{_safe_ident(time_col, dialect)} >= NOW() - INTERVAL '{hours} hours'"


def _is_time_column_name(col_name: str) -> bool:
    """Heuristic: does this column name suggest it holds time data?"""
    n = col_name.lower()
    time_patterns = ("date", "time", "timestamp", "day", "month", "year",
                     "created", "updated", "dt", "logged", "occurred")
    if any(p in n for p in time_patterns):
        return True
    # Check suffix patterns (avoid false positives like "status" matching "at")
    if n.endswith("_at") or n.endswith("_on"):
        return True
    return False


def _is_entity_column_name(col_name: str) -> bool:
    """Heuristic: does this column name suggest it holds entity/resource names?"""
    n = col_name.lower()
    entity_patterns = ("name", "type", "status", "label", "title", "category",
                       "equipment", "device", "host", "service", "resource", "tag")
    return any(p in n for p in entity_patterns)


def create_data_analyst_tools(user_id: int, context: str = "chat", db_connection_ids: list[str] | None = None) -> list[StructuredTool]:
    """Create all data-analyst tools bound to a specific user and context.

    Args:
        user_id: The authenticated user whose DB connections will be queried.
        context: "chat" or "reactive" — filters which connections are available.

    Returns:
        List of StructuredTool instances ready for DeepAgents registration.
    """

    # ── Tool 0: FAST PATH — Direct parameterized query (zero LLM) ─────

    async def _query_resource_data(
        resource: str,
        hours: int = 24,
        metric: str | None = None,
        connection_hint: str | None = None,
    ) -> str:
        """Query any database for recent resource data filtered by time window.

        Domain-agnostic: classifies columns by data type (timestamp/numeric/varchar),
        not by hardcoded names. Zero LLM calls — sub-second response.
        Use this FIRST for reactive events like 'last X hours of resource Y'.
        """
        async with get_session() as session:
            service = DataAnalystService(session)
            connections = await service._get_available_connections(user_id, context)
            if db_connection_ids:
                connections = [c for c in connections if c.id in db_connection_ids]
            if not connections:
                return "Error: No hay bases de datos disponibles."

            conn = connections[0]
            if connection_hint:
                match = next(
                    (c for c in connections if connection_hint.lower() in c.name.lower()),
                    None,
                )
                if match:
                    conn = match

            conn_ids = [c.id for c in connections if c.id == conn.id]
            schema_items = await service._retrieve_relevant_schema(
                user_id=user_id,
                question=f"{resource} {metric or ''}",
                connection_ids=conn_ids,
                top_k=20,
            )
            if not schema_items:
                return (
                    "No se encontraron tablas/columnas relevantes. "
                    "Usa execute_data_query como fallback."
                )

            # Classify columns by data type + name heuristics — domain-agnostic
            time_cols: list[tuple[str, str]] = []
            value_cols: list[tuple[str, str]] = []
            entity_cols: list[tuple[str, str]] = []
            tables_seen: set[str] = set()
            tables: list[str] = []

            for item in schema_items:
                dt = (item.data_type or "").lower()
                col_name = item.column_name
                if col_name is None:
                    continue
                if item.table_name not in tables_seen:
                    tables_seen.add(item.table_name)
                    tables.append(item.table_name)

                # Signal 1: SQL data type
                typed = False
                if any(t in dt for t in ("timestamp", "date", "time")):
                    time_cols.append((item.table_name, col_name))
                    typed = True
                elif any(t in dt for t in ("int", "numeric", "float", "decimal", "double", "real")):
                    value_cols.append((item.table_name, col_name))
                    typed = True
                elif any(t in dt for t in ("varchar", "text", "char", "string")):
                    entity_cols.append((item.table_name, col_name))
                    typed = True

                # Signal 2: Column name heuristics (fallback for ambiguous types like SQLite TEXT)
                if not typed and _is_time_column_name(col_name):
                    time_cols.append((item.table_name, col_name))
                elif not typed and _is_entity_column_name(col_name):
                    entity_cols.append((item.table_name, col_name))

            # Name-based fallback: if no time cols found by type, try name heuristics on ALL columns
            if not time_cols:
                for item in schema_items:
                    col_name = item.column_name
                    if col_name and _is_time_column_name(col_name):
                        time_cols.append((item.table_name, col_name))

            if not time_cols:
                return (
                    "Schema no tiene columnas de tipo fecha/hora. "
                    "Usa execute_data_query como fallback."
                )
            if not entity_cols:
                return (
                    "Schema no tiene columnas de texto/varchar para filtrar. "
                    "Usa execute_data_query como fallback."
                )

            table = tables[0]
            time_col = time_cols[0][1]
            entity_names = [c[1] for c in entity_cols]
            dialect = getattr(conn, "db_type", "postgresql") or "postgresql"

            # Build generic WHERE clauses from entity columns
            where_parts = [f"{_safe_ident(ecol, dialect)} LIKE '%{_safe_str(resource)}%'"
                           for ecol in entity_names[:2]]
            if metric:
                for ecol in entity_names:
                    if where_parts and ecol not in where_parts[0]:
                        where_parts.append(
                            f"{_safe_ident(ecol, dialect)} LIKE '%{_safe_str(metric)}%'"
                        )
                        break

            where_clause = " OR ".join(where_parts[:3])
            time_filter = _time_interval_sql(min(hours, 168), time_col, dialect)
            sql = (
                f"SELECT * FROM {_safe_ident(table, dialect)} "
                f"WHERE ({where_clause}) "
                f"AND {time_filter} "
                f"ORDER BY {_safe_ident(time_col, dialect)} DESC "
                f"LIMIT 500"
            )

            from backend.application.data_analysis.connector import DatabaseConnectionService
            db_svc = DatabaseConnectionService(session)
            try:
                result = await db_svc.execute_query(conn.id, user_id, sql)
            except Exception as exc:
                return (
                    f"Error ejecutando query rápida: {exc}. "
                    "Usa execute_data_query como fallback."
                )

            # If time-filtered query returns nothing, retry without time filter
            # to get ALL historical data for this resource
            if result.row_count == 0:
                sql_all = (
                    f"SELECT * FROM {_safe_ident(table, dialect)} "
                    f"WHERE ({where_clause}) "
                    f"ORDER BY {_safe_ident(time_col, dialect)} DESC "
                    f"LIMIT 500"
                )
                try:
                    result = await db_svc.execute_query(conn.id, user_id, sql_all)
                except Exception:
                    pass

            if result.row_count == 0:
                return (
                    f"Sin datos para resource='{resource}'"
                    + (f", metric='{metric}'" if metric else "")
                    + f" en últimas {hours}h ni en el histórico completo.\n"
                    + f"Tabla: {table}, SQL intentada: {sql}"
                )

            lines = [
                f"## Datos para: {resource}" + (f" / {metric}" if metric else ""),
                f"Ventana: {hours}h | Tabla: {table} | Filas: {result.row_count}",
                "",
                "| " + " | ".join(result.columns) + " |",
                "| " + " | ".join(["---"] * len(result.columns)) + " |",
            ]
            for row in result.rows[:20]:
                lines.append("| " + " | ".join(str(c) for c in row) + " |")
            if result.row_count > 20:
                lines.append(f"\n*... y {result.row_count - 20} filas más*")
            return "\n".join(lines)

    tool_query_resource_data = StructuredTool.from_function(
        coroutine=_query_resource_data,
        name="query_resource_data",
        description=(
            "RÁPIDO: Consulta directa parametrizada. CERO LLM — respuesta inmediata. "
            "Busca datos recientes de un recurso/entidad en cualquier base de datos. "
            "Clasifica columnas automáticamente por tipo de dato (fecha, numérico, texto). "
            "Usa esto SIEMPRE PRIMERO para consultas tipo 'últimas X horas del recurso Y'. "
            "Parámetros: resource (nombre de la entidad), hours (ventana en horas), "
            "metric (opcional, tipo de métrica a filtrar), connection_hint (opcional)."
        ),
    )

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

    tools = [
        tool_query_resource_data,   # FAST PATH — zero LLM, <1 second
        tool_list_connections,
        tool_retrieve_schema,
        tool_explain_sql,
    ]
    # execute_data_query is NL2SQL (slow) — only available in proactive (chat) context
    # In reactive context, query_resource_data is the ONLY query tool
    if context == "chat":
        tools.insert(3, tool_execute_query)

    return tools
