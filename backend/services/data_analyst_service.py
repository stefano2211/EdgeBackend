"""Data Analyst Service — core NL2SQL engine with self-correction and interpretation.

Pipeline:
  1. Discover available DB connections for the user
  2. Retrieve relevant schema items via semantic RAG
  3. Generate SQL using LLM + schema context + few-shot examples
  4. Execute with self-correction loop (max 3 attempts)
  5. Interpret results and generate business insights in Spanish

SOLID:
  - SRP: Only orchestrates the analysis pipeline.
  - DIP: Depends on DatabaseConnectionService and SchemaEmbeddingService abstractions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.logging import logging as _logging
from backend.database_connector.schemas import (
    SchemaDiscoveryResult,
    SchemaTable,
    SchemaColumn,
    QueryResult,
)
from backend.database_connector.service import DatabaseConnectionService
from backend.services.schema_embedding_service import SchemaEmbeddingService
from backend.services.data_analyst_schemas import (
    AnalystQuestion,
    AnalystResult,
    GeneratedSQL,
    SQLExecutionResult,
    QueryOutput,
    SchemaContextItem,
    ConnectionSummary,
    DataAnalystError,
)

logger = _logging.getLogger(__name__)

# Few-shot examples to improve NL2SQL quality
# These are domain-agnostic and teach the LLM the expected output format.
_FEW_SHOT_EXAMPLES = """
Ejemplo 1:
Pregunta: "Cuántos usuarios se registraron en enero 2024?"
Schema relevante:
  - Tabla users: id (PK, uuid), email (varchar), created_at (timestamp), role (varchar)
SQL generada:
SELECT COUNT(*) AS total_usuarios
FROM users
WHERE created_at >= '2024-01-01' AND created_at < '2024-02-01';

Ejemplo 2:
Pregunta: "Top 5 productos más vendidos por cantidad"
Schema relevante:
  - Tabla ventas: id (PK), producto_id (FK → productos.id), cantidad (int), fecha (timestamp)
  - Tabla productos: id (PK), nombre (varchar), precio (decimal)
SQL generada:
SELECT p.nombre, SUM(v.cantidad) AS total_vendido
FROM ventas v
JOIN productos p ON v.producto_id = p.id
GROUP BY p.id, p.nombre
ORDER BY total_vendido DESC
LIMIT 5;

Ejemplo 3:
Pregunta: "Clientes que no han comprado en los últimos 6 meses"
Schema relevante:
  - Tabla clientes: id (PK), nombre (varchar), email (varchar)
  - Tabla pedidos: id (PK), cliente_id (FK → clientes.id), fecha (timestamp)
SQL generada:
SELECT c.id, c.nombre, c.email, MAX(p.fecha) AS ultima_compra
FROM clientes c
LEFT JOIN pedidos p ON c.id = p.cliente_id
GROUP BY c.id, c.nombre, c.email
HAVING MAX(p.fecha) < CURRENT_DATE - INTERVAL '6 months'
   OR MAX(p.fecha) IS NULL;
"""

_MAX_RETRIES = 3
_READ_ONLY_HINTS = (
    "SELECT", "FROM", "WHERE", "JOIN", "LEFT JOIN", "INNER JOIN",
    "GROUP BY", "ORDER BY", "LIMIT", "HAVING", "COUNT", "SUM", "AVG",
    "MIN", "MAX", "DISTINCT", "ON", "AS", "AND", "OR", "NOT", "IN",
    "BETWEEN", "LIKE", "IS NULL", "IS NOT NULL", "CASE", "WHEN", "THEN",
    "ELSE", "END", "WITH", "CTE", "UNION", "INTERSECT", "EXCEPT",
)


class DataAnalystService:
    """Natural-language-to-SQL analysis service with auto-correction."""

    def __init__(
        self,
        session: AsyncSession,
        db_service: DatabaseConnectionService | None = None,
        embedding_service: SchemaEmbeddingService | None = None,
    ) -> None:
        self._session = session
        self._db_service = db_service or DatabaseConnectionService(session)
        self._embedding_service = embedding_service or SchemaEmbeddingService()

    # ═══════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════

    async def ask(self, question: AnalystQuestion, user_id: int) -> AnalystResult:
        """Answer a natural-language data question via NL2SQL pipeline."""
        start = datetime.now(timezone.utc)

        try:
            # 1. Discover available connections
            connections = await self._get_available_connections(
                user_id, question.context
            )
            if not connections:
                return AnalystResult(
                    question=question.question,
                    status="failed",
                    error="No hay bases de datos conectadas disponibles.",
                )

            # 2. Filter by explicit connection_ids if provided
            target_connections = connections
            if question.connection_ids:
                target_connections = [
                    c for c in connections if c.id in question.connection_ids
                ]

            # 3. If connection_hint provided, further filter
            if question.connection_hint:
                hinted = [
                    c for c in target_connections
                    if question.connection_hint.lower() in c.name.lower()
                ]
                if hinted:
                    target_connections = hinted

            connection_ids = [c.id for c in target_connections]

            # 3. Retrieve relevant schema via semantic RAG
            schema_items = await self._retrieve_relevant_schema(
                user_id=user_id,
                question=question.question,
                connection_ids=connection_ids,
            )

            if not schema_items:
                return AnalystResult(
                    question=question.question,
                    status="failed",
                    error=(
                        "No se encontraron tablas o columnas relevantes en las bases de datos. "
                        "¿Quizás la pregunta no está relacionada con los datos disponibles?"
                    ),
                )

            # 4. Generate SQL
            generated = await self._generate_sql(
                question=question.question,
                schema_items=schema_items,
                connections=target_connections,
            )

            if not generated:
                return AnalystResult(
                    question=question.question,
                    status="failed",
                    error="No se pudo generar una consulta SQL a partir de la pregunta.",
                )

            # 5. Execute with self-correction
            execution = await self._execute_with_retry(
                sql=generated.sql,
                connection_id=generated.connection_id,
                connection_name=generated.connection_name,
            )

            elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

            if not execution.success:
                return AnalystResult(
                    question=question.question,
                    sql=execution.final_sql,
                    status="failed",
                    error=execution.error,
                    connection_used=execution.connection_name,
                    connection_id=execution.connection_id,
                    execution_time_ms=elapsed,
                    retries=execution.attempts - 1,
                )

            # 6. Interpret results
            insights = await self._interpret_results(
                question=question.question,
                sql=execution.final_sql,
                result=execution.data,
            )

            return AnalystResult(
                question=question.question,
                sql=execution.final_sql,
                sql_explanation=generated.explanation,
                results=execution.data,
                insights=insights,
                connection_used=execution.connection_name,
                connection_id=execution.connection_id,
                execution_time_ms=elapsed,
                retries=execution.attempts - 1,
                status="success",
            )

        except Exception as exc:
            logger.exception("Data analyst pipeline failed for user=%s: %s", user_id, exc)
            elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            return AnalystResult(
                question=question.question,
                status="failed",
                error=f"Error interno del pipeline: {exc}",
                execution_time_ms=elapsed,
            )

    async def explain_sql(self, sql: str, connection_id: str, user_id: int) -> str:
        """Explain what a SQL query does in plain Spanish."""
        client = self._get_llm_client()
        prompt = (
            "Explica esta consulta SQL en español simple, como si se lo explicaras "
            "a un analista de negocio que no conoce SQL:\n\n"
            f"```sql\n{sql}\n```\n\n"
            "Tu explicación debe incluir:\n"
            "1. Qué información busca la consulta\n"
            "2. De qué tablas obtiene los datos\n"
            "3. Qué filtros o agrupaciones aplica\n"
            "Responde en 3-5 oraciones."
        )
        response = await client.chat_completion(
            messages=[
                {"role": "system", "content": "Eres un experto en bases de datos. Explicas SQL de forma clara."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
            stream=False,
        )
        return (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "No se pudo generar la explicación.")
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  STEP 1 — CONNECTION DISCOVERY
    # ═══════════════════════════════════════════════════════════════════════

    async def _get_available_connections(
        self, user_id: int, context: str
    ) -> list[ConnectionSummary]:
        """Fetch user's DB connections that are available in the given context."""
        conns = await self._db_service.list_connections(user_id, context)
        return [
            ConnectionSummary(
                id=c.id,
                name=c.name,
                db_type=c.db_type,
                description=f"Base de datos {c.db_type} en {c.host}:{c.port}",
                status=c.status,
                available_in_chat=c.available_in_chat,
                available_in_reactive=c.available_in_reactive,
            )
            for c in conns
            if c.status == "connected"
        ]

    # ═══════════════════════════════════════════════════════════════════════
    #  STEP 2 — SCHEMA RAG RETRIEVAL
    # ═══════════════════════════════════════════════════════════════════════

    async def _retrieve_relevant_schema(
        self,
        user_id: int,
        question: str,
        connection_ids: list[str],
        top_k: int = 15,
    ) -> list[SchemaContextItem]:
        """Semantic search for schema items relevant to the question."""
        results = await self._embedding_service.search_relevant_schema(
            user_id=user_id,
            question=question,
            connection_ids=connection_ids,
            top_k=top_k,
        )
        return [SchemaContextItem(**r, relevance_score=r.get("score", 0.0)) for r in results]

    # ═══════════════════════════════════════════════════════════════════════
    #  STEP 3 — SQL GENERATION
    # ═══════════════════════════════════════════════════════════════════════

    async def _generate_sql(
        self,
        question: str,
        schema_items: list[SchemaContextItem],
        connections: list[ConnectionSummary],
    ) -> GeneratedSQL | None:
        """Generate SQL from NL + schema context using LLM."""
        client = self._get_llm_client()

        # Build schema context text
        schema_text = self._build_schema_context(schema_items)

        # Pick the most relevant connection (the one with most schema hits)
        conn_scores: dict[str, int] = {}
        for item in schema_items:
            conn_scores[item.connection_id] = conn_scores.get(item.connection_id, 0) + 1
        best_conn_id = max(conn_scores, key=conn_scores.get) if conn_scores else None
        best_conn = next(
            (c for c in connections if c.id == best_conn_id), connections[0]
        )

        prompt = self._build_nl2sql_prompt(question, schema_text, best_conn.db_type)

        try:
            response = await client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres un experto en SQL. Generas consultas SELECT read-only "
                            "precisas y eficientes. Respondes ÚNICAMENTE con un JSON válido."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1200,
                stream=False,
            )

            raw = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return self._parse_generated_sql(raw, best_conn.id, best_conn.name)

        except Exception as exc:
            logger.warning("SQL generation failed: %s", exc)
            return None

    # ═══════════════════════════════════════════════════════════════════════
    #  STEP 4 — EXECUTION WITH SELF-CORRECTION
    # ═══════════════════════════════════════════════════════════════════════

    async def _execute_with_retry(
        self,
        sql: str,
        connection_id: str,
        connection_name: str,
    ) -> SQLExecutionResult:
        """Execute SQL with automatic retry on transient/fatal errors."""
        start = datetime.now(timezone.utc)
        current_sql = sql
        last_error = ""

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                # Quick safety check (should be redundant with execute_query, but belt+braces)
                if not self._is_safe_sql(current_sql):
                    return SQLExecutionResult(
                        final_sql=current_sql,
                        success=False,
                        error="La consulta generada no es read-only (contiene DDL/DML).",
                        connection_id=connection_id,
                        connection_name=connection_name,
                        elapsed_ms=0,
                        attempts=attempt,
                    )

                # Execute via DatabaseConnectionService
                result: QueryResult = await self._db_service.execute_query(
                    connection_id=connection_id,
                    user_id=0,  # user_id validated upstream
                    sql=current_sql,
                )

                elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

                return SQLExecutionResult(
                    final_sql=current_sql,
                    success=True,
                    data=QueryOutput(
                        columns=result.columns,
                        rows=result.rows,
                        row_count=result.row_count,
                        truncated=result.truncated,
                    ),
                    connection_id=connection_id,
                    connection_name=connection_name,
                    elapsed_ms=elapsed,
                    attempts=attempt,
                )

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "SQL execution attempt %d/%d failed: %s",
                    attempt,
                    _MAX_RETRIES,
                    last_error,
                )

                if attempt < _MAX_RETRIES:
                    # Ask LLM to fix the SQL
                    fixed = await self._fix_sql(current_sql, last_error)
                    if fixed and fixed != current_sql:
                        current_sql = fixed
                        logger.info("SQL corrected by LLM, retrying...")
                    else:
                        break  # Can't fix it
                else:
                    break

        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        return SQLExecutionResult(
            final_sql=current_sql,
            success=False,
            error=f"Falló después de {attempt} intentos. Último error: {last_error}",
            connection_id=connection_id,
            connection_name=connection_name,
            elapsed_ms=elapsed,
            attempts=attempt,
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  STEP 5 — RESULT INTERPRETATION
    # ═══════════════════════════════════════════════════════════════════════

    async def _interpret_results(
        self,
        question: str,
        sql: str,
        result: QueryOutput | None,
    ) -> str:
        """Generate business insights from query results."""
        if not result or result.row_count == 0:
            return "La consulta no devolvió resultados. Esto puede deberse a que no hay datos que coincidan con los criterios."

        client = self._get_llm_client()

        # Build a compact representation of the data for the LLM
        data_summary = self._summarize_data(result)

        prompt = (
            f"Analiza estos resultados de una consulta de base de datos y genera insights "
            f"en español para un usuario de negocio.\n\n"
            f"Pregunta original: {question}\n\n"
            f"SQL ejecutada: {sql}\n\n"
            f"Resultados:\n{data_summary}\n\n"
            f"Genera 2-4 observaciones relevantes. Incluye tendencias, anomalías o recomendaciones "
            f"cuando sea apropiado. Sé conciso y accionable."
        )

        try:
            response = await client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres un analista de datos senior. Interpretas resultados SQL "
                            "y generas insights claros y accionables en español."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=600,
                stream=False,
            )
            return (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "No se pudieron generar insights.")
            )
        except Exception as exc:
            logger.warning("Result interpretation failed: %s", exc)
            return "No se pudieron generar insights automáticos."

    # ═══════════════════════════════════════════════════════════════════════
    #  PRIVATE HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _get_llm_client():
        """Lazy import to avoid circular deps at module load time."""
        from backend.ia.llm_client import get_llm_client
        return get_llm_client()

    @staticmethod
    def _build_schema_context(items: list[SchemaContextItem]) -> str:
        """Convert schema items into a structured text for the LLM prompt."""
        # Group by table for readability
        tables: dict[str, dict] = {}
        for item in items:
            if item.table_name not in tables:
                tables[item.table_name] = {
                    "description": "",
                    "columns": [],
                    "connection": item.connection_name,
                }
            if item.type == "table":
                tables[item.table_name]["description"] = item.description or ""
            else:
                col_info = f"  - {item.column_name} ({item.data_type})"
                if item.is_pk:
                    col_info += " [PK]"
                if item.fk_to:
                    col_info += f" [FK → {item.fk_to}]"
                if item.description:
                    col_info += f": {item.description}"
                tables[item.table_name]["columns"].append(col_info)

        lines: list[str] = []
        for table_name, info in tables.items():
            lines.append(f"\nTabla: {table_name}")
            if info["description"]:
                lines.append(f"  Descripción: {info['description']}")
            if info["columns"]:
                lines.extend(info["columns"])
        return "\n".join(lines)

    @staticmethod
    def _build_nl2sql_prompt(question: str, schema_text: str, db_type: str) -> str:
        """Build the full NL2SQL prompt with few-shot examples and schema context."""
        dialect = "PostgreSQL" if db_type == "postgresql" else "MySQL"
        return (
            f"Genera una consulta SQL read-only para responder a la siguiente pregunta.\n\n"
            f"Base de datos: {dialect}\n\n"
            f"Pregunta: {question}\n\n"
            f"Schema relevante (solo las tablas y columnas más pertinentes):\n"
            f"{schema_text}\n\n"
            f"Ejemplos de consultas similares:\n{_FEW_SHOT_EXAMPLES}\n\n"
            f"INSTRUCCIONES:\n"
            f"- Genera SOLO una consulta SELECT (read-only).\n"
            f"- No uses INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE.\n"
            f"- Si la pregunta requiere unir tablas, usa JOINs explícitos.\n"
            f"- Usa LIMIT 1000 como máximo a menos que se pida explícitamente más.\n"
            f"- Responde con este formato JSON exacto:\n"
            f'{{"sql": "SELECT ...", "explanation": "Esta consulta busca ...", "confidence": "high|medium|low", "tables": ["tabla1", "tabla2"]}}\n'
        )

    @staticmethod
    def _parse_generated_sql(
        raw: str, connection_id: str, connection_name: str
    ) -> GeneratedSQL | None:
        """Parse the LLM JSON response into GeneratedSQL."""
        import json

        cleaned = raw.strip()
        # Strip markdown fences
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract SQL from raw text if JSON parse fails
            sql = DataAnalystService._extract_sql_fallback(raw)
            if sql:
                return GeneratedSQL(
                    sql=sql,
                    connection_id=connection_id,
                    connection_name=connection_name,
                    explanation="SQL extraída del formato no estructurado.",
                    confidence="low",
                )
            return None

        sql = data.get("sql", "")
        if not sql:
            return None

        return GeneratedSQL(
            sql=sql,
            connection_id=connection_id,
            connection_name=connection_name,
            explanation=data.get("explanation"),
            confidence=data.get("confidence", "medium"),
            targeted_tables=data.get("tables", []),
        )

    @staticmethod
    def _extract_sql_fallback(text: str) -> str | None:
        """Last-resort SQL extraction from free-form text."""
        import re
        # Look for SELECT ... ; pattern
        match = re.search(r"SELECT\s+.+?;", text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(0)
        return None

    @staticmethod
    def _is_safe_sql(sql: str) -> bool:
        """Quick heuristic check for read-only queries."""
        upper = sql.upper().strip()
        # Must start with SELECT or WITH
        if not (upper.startswith("SELECT") or upper.startswith("WITH")):
            return False
        # No DDL/DML keywords
        forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"}
        tokens = re.findall(r"\b[A-Z]+\b", upper)
        return not any(t in forbidden for t in tokens)

    async def _fix_sql(self, sql: str, error: str) -> str | None:
        """Ask LLM to fix a broken SQL query."""
        client = self._get_llm_client()
        prompt = (
            f"Corrige esta consulta SQL que falló con el siguiente error:\n\n"
            f"SQL original:\n```sql\n{sql}\n```\n\n"
            f"Error: {error}\n\n"
            f"Genera SOLO la consulta SQL corregida, sin explicaciones adicionales. "
            f"Mantén la lógica original y corrige solo el error."
        )
        try:
            response = await client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un experto en SQL. Corrige errores de sintaxis y semántica.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=800,
                stream=False,
            )
            raw = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            fixed = DataAnalystService._extract_sql_fallback(raw)
            return fixed
        except Exception as exc:
            logger.warning("SQL fix attempt failed: %s", exc)
            return None

    @staticmethod
    def _summarize_data(result: QueryOutput) -> str:
        """Create a compact text summary of query results for the LLM."""
        lines = [f"Columnas: {', '.join(result.columns)}", f"Filas: {result.row_count}"]
        if result.truncated:
            lines.append("(Resultados truncados)")
        # Show first 10 rows
        for i, row in enumerate(result.rows[:10]):
            lines.append(f"  Fila {i+1}: {row}")
        if result.row_count > 10:
            lines.append(f"  ... y {result.row_count - 10} filas más")
        return "\n".join(lines)
