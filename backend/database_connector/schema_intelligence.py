"""Schema intelligence engine — auto-discovery of relationships, stats, and descriptions.

Provides rich metadata beyond basic table/column names:
  - Foreign key detection and relationship mapping
  - Row count estimation per table
  - Sample values for categorical columns
  - Cardinality analysis (high/low)
  - Auto-generated Spanish descriptions via LLM
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.core.logging import logging as _logging
from backend.database_connector.schemas import SchemaColumn, SchemaTable

logger = _logging.getLogger(__name__)

# Categorical type heuristics for sample-value extraction
_CATEGORICAL_TYPES = {
    "character varying",
    "varchar",
    "text",
    "char",
    "character",
    "enum",
    "uuid",
    "boolean",
    "bool",
}

# Threshold for low cardinality (distinct values / total rows < this)
_LOW_CARDINALITY_RATIO = 0.05


@dataclass
class EnrichedColumn:
    name: str
    type: str
    nullable: bool = False
    is_pk: bool = False
    fk_to: str | None = None
    description: str | None = None
    cardinality: str = "unknown"  # "high" | "medium" | "low"
    sample_values: list[str] = field(default_factory=list)


@dataclass
class EnrichedTable:
    name: str
    description: str | None = None
    row_count: int | None = None
    columns: list[EnrichedColumn] = field(default_factory=list)


class SchemaIntelligence:
    """Enriches discovered schema with relationships, stats, and auto-descriptions."""

    def __init__(self, *, max_sample_values: int = 20, llm_max_tables: int = 30) -> None:
        self.max_sample_values = max_sample_values
        self.llm_max_tables = llm_max_tables

    # ═══════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════

    async def enrich(
        self,
        connection,
        engine: AsyncEngine,
        tables: list[SchemaTable],
        auto_describe: bool = True,
    ) -> list[EnrichedTable]:
        """Enrich a list of SchemaTable objects with full intelligence.

        Args:
            connection: DatabaseConnection instance (for db_type, schema_name, etc.)
            engine: SQLAlchemy async engine bound to the target DB.
            tables: Basic schema tables from the existing discovery flow.
            auto_describe: Whether to call the LLM for auto-descriptions.

        Returns:
            List of EnrichedTable with FKs, row counts, samples, and descriptions.
        """
        db_type = connection.db_type
        schema_name = connection.schema_name or "public"
        db_name = connection.database_name

        enriched_tables: list[EnrichedTable] = []

        async with engine.connect() as conn:
            # 1. Fetch all FK relationships in one query (fast)
            fk_map = await self._fetch_foreign_keys(conn, db_type, schema_name, db_name)

            for table in tables:
                e_table = EnrichedTable(name=table.name)

                # 2. Row count
                e_table.row_count = await self._get_row_count(conn, db_type, table.name)

                # 3. Enrich each column
                for col in table.columns:
                    e_col = EnrichedColumn(
                        name=col.name,
                        type=col.type,
                        nullable=col.nullable,
                        is_pk=col.is_pk,
                        fk_to=fk_map.get((table.name, col.name)),
                    )

                    # 4. Sample values + cardinality (only for categorical-ish types)
                    if self._is_categorical_type(col.type):
                        samples, cardinality = await self._analyze_column(
                            conn, db_type, table.name, col.name, e_table.row_count
                        )
                        e_col.sample_values = samples
                        e_col.cardinality = cardinality
                    else:
                        # For numeric/timestamp types, estimate cardinality from row count
                        e_col.cardinality = self._estimate_cardinality(
                            e_table.row_count, col.type
                        )

                    e_table.columns.append(e_col)

                enriched_tables.append(e_table)

        # 5. Auto-generate descriptions via LLM (batch by batch to avoid huge prompts)
        if auto_describe:
            await self._auto_describe_tables(enriched_tables)

        return enriched_tables

    # ═══════════════════════════════════════════════════════════════════════
    #  FK DETECTION
    # ═══════════════════════════════════════════════════════════════════════

    async def _fetch_foreign_keys(
        self, conn, db_type: str, schema_name: str, db_name: str
    ) -> dict[tuple[str, str], str]:
        """Return mapping {(table_name, column_name): "target_table.target_col"}."""
        fk_map: dict[tuple[str, str], str] = {}

        if db_type == "postgresql":
            sql = text("""
                SELECT
                    kcu.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.key_column_usage kcu
                JOIN information_schema.table_constraints tc
                    ON kcu.constraint_name = tc.constraint_name
                    AND kcu.table_schema = tc.table_schema
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND kcu.table_schema = :schema
            """)
            result = await conn.execute(sql, {"schema": schema_name})
            for row in result.fetchall():
                table_name, col_name, fk_table, fk_col = row
                fk_map[(table_name, col_name)] = f"{fk_table}.{fk_col}"

        else:  # mysql
            sql = text("""
                SELECT
                    kcu.table_name,
                    kcu.column_name,
                    kcu.referenced_table_name,
                    kcu.referenced_column_name
                FROM information_schema.key_column_usage kcu
                JOIN information_schema.table_constraints tc
                    ON kcu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND kcu.table_schema = :db
            """)
            result = await conn.execute(sql, {"db": db_name})
            for row in result.fetchall():
                table_name, col_name, fk_table, fk_col = row
                if fk_table and fk_col:
                    fk_map[(table_name, col_name)] = f"{fk_table}.{fk_col}"

        logger.info("Discovered %d foreign key relationships", len(fk_map))
        return fk_map

    # ═══════════════════════════════════════════════════════════════════════
    #  ROW COUNTS
    # ═══════════════════════════════════════════════════════════════════════

    async def _get_row_count(self, conn, db_type: str, table_name: str) -> int | None:
        """Fast row count estimation."""
        try:
            if db_type == "postgresql":
                # pg_class.reltuples is fast but approximate; fall back to COUNT if 0
                sql = text("""
                    SELECT reltuples::bigint
                    FROM pg_class
                    WHERE relname = :table AND relkind = 'r'
                """)
                result = await conn.execute(sql, {"table": table_name})
                row = result.scalar()
                if row and row > 0:
                    return int(row)
                # Fallback to exact count for small tables
                exact = await conn.execute(
                    text(f'SELECT COUNT(*) FROM "{table_name}"')
                )
                return exact.scalar()
            else:
                # MySQL: SHOW TABLE STATUS or exact count
                sql = text("""
                    SELECT table_rows
                    FROM information_schema.tables
                    WHERE table_name = :table AND table_schema = DATABASE()
                """)
                result = await conn.execute(sql, {"table": table_name})
                row = result.scalar()
                if row and row > 0:
                    return int(row)
                exact = await conn.execute(
                    text(f"SELECT COUNT(*) FROM `{table_name}`")
                )
                return exact.scalar()
        except Exception as exc:
            logger.warning("Row count failed for %s: %s", table_name, exc)
            return None

    # ═══════════════════════════════════════════════════════════════════════
    #  COLUMN ANALYSIS (samples + cardinality)
    # ═══════════════════════════════════════════════════════════════════════

    async def _analyze_column(
        self,
        conn,
        db_type: str,
        table_name: str,
        column_name: str,
        row_count: int | None,
    ) -> tuple[list[str], str]:
        """Return (sample_values, cardinality_label) for a categorical column."""
        try:
            if db_type == "postgresql":
                sample_sql = text(f"""
                    SELECT DISTINCT "{column_name}"
                    FROM "{table_name}"
                    WHERE "{column_name}" IS NOT NULL
                    LIMIT :limit
                """)
            else:
                sample_sql = text(f"""
                    SELECT DISTINCT `{column_name}`
                    FROM `{table_name}`
                    WHERE `{column_name}` IS NOT NULL
                    LIMIT :limit
                """)

            result = await conn.execute(
                sample_sql, {"limit": self.max_sample_values}
            )
            samples = [str(row[0]) for row in result.fetchall() if row[0] is not None]

            # Cardinality
            cardinality = self._classify_cardinality(len(samples), row_count)
            return samples, cardinality

        except Exception as exc:
            logger.debug(
                "Sample analysis failed for %s.%s: %s", table_name, column_name, exc
            )
            return [], "unknown"

    # ═══════════════════════════════════════════════════════════════════════
    #  AUTO-DESCRIPTION via LLM
    # ═══════════════════════════════════════════════════════════════════════

    async def _auto_describe_tables(self, tables: list[EnrichedTable]) -> None:
        """Generate Spanish descriptions for tables and columns using LLM.

        Batches tables to avoid massive prompts. Only describes up to
        llm_max_tables to keep latency reasonable.
        """
        try:
            from backend.ia.llm_client import get_llm_client
        except Exception:
            logger.warning("LLM client not available; skipping auto-descriptions")
            return

        client = get_llm_client()

        # Process in batches of 5 tables
        batch_size = 5
        for i in range(0, len(tables), batch_size):
            batch = tables[i : i + batch_size]
            if i >= self.llm_max_tables:
                logger.info(
                    "Auto-description capped at %d tables", self.llm_max_tables
                )
                break

            prompt = self._build_description_prompt(batch)
            try:
                response = await client.chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Eres un experto en bases de datos. "
                                "Genera descripciones cortas y útiles en español. "
                                "Responde ÚNICAMENTE con un JSON válido."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=800,
                    stream=False,
                )
                raw = (
                    response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                await self._apply_descriptions(batch, raw)
            except Exception as exc:
                logger.warning("Auto-description batch failed: %s", exc)

    def _build_description_prompt(self, tables: list[EnrichedTable]) -> str:
        """Build a prompt that asks the LLM to describe tables and columns."""
        lines = [
            "Describe cada tabla y sus columnas en español. "
            "Responde con este formato JSON exacto:\n",
            "{\"tablas\": [{\"nombre\": \"...\", \"descripcion\": \"...\", "
            "\"columnas\": [{\"nombre\": \"...\", \"descripcion\": \"...\"}]}]}\n",
            "Tablas disponibles:\n",
        ]
        for t in tables:
            lines.append(f"\nTabla: {t.name}")
            if t.row_count is not None:
                lines.append(f"  Filas aprox: {t.row_count}")
            for col in t.columns:
                fk_hint = f" (FK → {col.fk_to})" if col.fk_to else ""
                pk_hint = " [PK]" if col.is_pk else ""
                lines.append(
                    f"  - {col.name}: {col.type}{pk_hint}{fk_hint}"
                )
        return "\n".join(lines)

    async def _apply_descriptions(
        self, tables: list[EnrichedTable], raw_response: str
    ) -> None:
        """Parse LLM JSON response and apply descriptions to tables/columns."""
        import json

        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            # Strip markdown fences
            lines = cleaned.splitlines()
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse auto-description JSON: %s", raw_response[:200])
            return

        desc_tables = {t["nombre"]: t for t in data.get("tablas", [])}

        for table in tables:
            t_data = desc_tables.get(table.name)
            if not t_data:
                continue
            table.description = t_data.get("descripcion") or table.description
            col_descs = {c["nombre"]: c for c in t_data.get("columnas", [])}
            for col in table.columns:
                col.description = col_descs.get(col.name, {}).get("descripcion")

    # ═══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _is_categorical_type(data_type: str) -> bool:
        """Heuristic: is this type likely to have meaningful distinct values?"""
        type_lower = data_type.lower()
        return any(ct in type_lower for ct in _CATEGORICAL_TYPES)

    @staticmethod
    def _classify_cardinality(
        distinct_count: int, row_count: int | None
    ) -> str:
        """Label cardinality based on distinct/total ratio."""
        if row_count is None or row_count == 0:
            return "unknown"
        ratio = distinct_count / row_count
        if ratio < _LOW_CARDINALITY_RATIO:
            return "low"
        if ratio < 0.5:
            return "medium"
        return "high"

    @staticmethod
    def _estimate_cardinality(row_count: int | None, data_type: str) -> str:
        """Estimate cardinality for non-categorical types."""
        type_lower = data_type.lower()
        if row_count is None:
            return "unknown"
        # IDs, timestamps, serials are usually high cardinality
        if any(t in type_lower for t in ("serial", "int", "bigint", "uuid", "timestamp", "date", "time")):
            return "high"
        if "bool" in type_lower:
            return "low"
        return "medium"

    # ═══════════════════════════════════════════════════════════════════════
    #  CONVERSION: EnrichedTable → SchemaTable (for backward compat)
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def to_schema_table(enriched: EnrichedTable) -> SchemaTable:
        """Convert an EnrichedTable back to the standard SchemaTable Pydantic model."""
        columns = [
            SchemaColumn(
                name=c.name,
                type=c.type,
                nullable=c.nullable,
                is_pk=c.is_pk,
                fk_ref=c.fk_to,
                description=c.description,
            )
            for c in enriched.columns
        ]
        return SchemaTable(
            name=enriched.name,
            description=enriched.description,
            row_count=enriched.row_count,
            columns=columns,
        )
