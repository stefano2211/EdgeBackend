"""Query enhancement service for improved RAG retrieval.

Addresses the semantic gap between short/ambiguous user queries and
long, structured documents in the knowledge base. Two techniques:

1. Multi-Query: generates N query variations for broader recall.
2. HyDE (Hypothetical Document Embeddings): generates a hypothetical
   answer document, whose embedding is closer to real documents than
   the original question embedding.

Applied selectively: only activated when initial retrieval yields
low-quality results or the query is detected as ambiguous.

Uses the local Ollama LLM to avoid external API dependencies.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from src.core.config import settings
from src.core.logging import logging

logger = logging.getLogger(__name__)


class QueryEnhancerPort(Protocol):
    """Abstract query enhancer for dependency inversion."""

    async def enhance(self, query: str) -> list[str]:
        ...


class LLMQueryEnhancer:
    """Generate query variations using the local LLM (Ollama).

    Combines multi-query expansion and HyDE for maximum recall
    on complex or ambiguous queries.
    """

    async def _call_llm(self, prompt: str) -> str:
        """Call the local LLM for query enhancement."""
        try:
            from src.ia.llm_client import get_llm_client

            client = get_llm_client()
            response = await client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                max_tokens=300,
                temperature=0.7,
            )
            # Parse OpenAI-compatible response format
            choices = response.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            return ""
        except Exception as e:
            logger.warning("LLM query enhancement failed: %s", e)
            return ""

    async def multi_query(self, query: str, n: int = 3) -> list[str]:
        """Generate n query variations for broader retrieval coverage.

        The LLM rephrases the query from different angles, adding
        domain-specific terminology and synonyms.
        """
        prompt = (
            f"Generate exactly {n} different search queries that would help find "
            f"documents relevant to the following question. Each query should approach "
            f"the topic from a different angle or use different terminology. "
            f"Return ONLY the queries, one per line, no numbering.\n\n"
            f"Original question: {query}"
        )
        result = await self._call_llm(prompt)
        if not result:
            return []

        queries = [q.strip() for q in result.strip().split("\n") if q.strip()]
        return queries[:n]

    async def hyde(self, query: str) -> str:
        """Generate a hypothetical document that answers the query.

        The embedding of this hypothetical document is often more
        semantically similar to real documents than the question embedding.
        """
        prompt = (
            "Write a short, factual paragraph (50-100 words) that would be found "
            "in a technical document and directly answers the following question. "
            "Be specific and use technical terminology. "
            "Return ONLY the paragraph, no preamble.\n\n"
            f"Question: {query}"
        )
        result = await self._call_llm(prompt)
        return result if result else ""

    async def enhance(self, query: str) -> list[str]:
        """Combine multi-query + HyDE for maximum recall.

        Returns the original query plus all enhanced variations.
        The original is always first to preserve user intent.
        """
        # Run multi-query and HyDE in parallel
        multi_task = asyncio.create_task(self.multi_query(query))
        hyde_task = asyncio.create_task(self.hyde(query))

        variations = await multi_task
        hypothetical = await hyde_task

        enhanced = [query]
        if hypothetical:
            enhanced.append(hypothetical)
        enhanced.extend(variations)

        logger.debug(
            "Enhanced query into %d variations (original + %d multi + %s HyDE)",
            len(enhanced),
            len(variations),
            "1" if hypothetical else "0",
        )
        return enhanced


class NoOpQueryEnhancer:
    """Passthrough enhancer that returns the original query unchanged."""

    async def enhance(self, query: str) -> list[str]:
        return [query]


def get_query_enhancer() -> LLMQueryEnhancer | NoOpQueryEnhancer:
    """Factory: return the appropriate query enhancer based on settings."""
    if settings.QUERY_ENHANCEMENT_ENABLED:
        return LLMQueryEnhancer()
    return NoOpQueryEnhancer()
