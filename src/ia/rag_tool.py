"""RAG tool — real document retrieval from Qdrant.

Orchestrates: embed query → search vectors → format context for LLM.
"""

from src.core.logging import logging
from src.services.embedding_service import embed_query
from src.persistencia.vector import VectorRepository
from src.persistencia.vector.vector_store_port import VectorStorePort

logger = logging.getLogger(__name__)

# Confidence threshold: chunks below this similarity score are dropped
# to reduce hallucinations from irrelevant context.
_MIN_RELEVANCE_SCORE = 0.35


def _format_context(
    results: list[dict],
    query: str,
    *,
    min_score: float = _MIN_RELEVANCE_SCORE,
) -> str | None:
    """Format retrieved chunks into a context string for the LLM.

    Drops low-relevance chunks and orders by score (descending).
    Includes page numbers and source filenames for traceability.
    """
    # Filter and sort by relevance
    filtered = [r for r in results if r.get("score", 0.0) >= min_score]
    if not filtered:
        logger.debug("All RAG chunks scored below %.2f; dropping context", min_score)
        return None

    # Sort by score descending so the most relevant chunk comes first
    filtered.sort(key=lambda r: r.get("score", 0.0), reverse=True)

    sources: list[str] = []
    for i, r in enumerate(filtered, start=1):
        filename = r.get("filename") or "unknown"
        page = r.get("page_number")
        score = r.get("score", 0.0)

        attrs = f'rank="{i}" doc="{filename}" score="{score:.3f}"'
        if page is not None:
            attrs += f' page="{page}"'

        sources.append(
            f"<source {attrs}>\n"
            f"[Chunk {r.get('chunk_index', '?')}]: {r['text']}\n"
            f"</source>"
        )

    context = "\n\n".join(sources)

    return (
        "You are a helpful assistant. Answer the question using ONLY the "
        "retrieved sources below. If the answer is not found in the sources, "
        "say you do not know. Do not make up facts.\n\n"
        f"Sources:\n{context}\n\n"
        f"Question: {query}"
    )


async def rag_retrieve(
    knowledge_base_id: str,
    query: str,
    top_k: int = 5,
    filter_doc_ids: list[int | str] | None = None,
    vector_repo: VectorStorePort | None = None,
    min_score: float = _MIN_RELEVANCE_SCORE,
) -> str | None:
    """
    Search Qdrant for relevant document chunks and return formatted context.

    Args:
        knowledge_base_id: Target knowledge base / Qdrant collection.
        query: User query string.
        top_k: Number of chunks to retrieve.
        filter_doc_ids: Optional doc-id filter.
        vector_repo: Optional vector store implementation (for DI/testing).
        min_score: Minimum cosine-similarity score to include a chunk.

    Returns:
        Formatted context string, or None if no relevant chunks found.
        Never raises — returns None on any error to avoid breaking the chat.
    """
    repo = vector_repo if vector_repo is not None else VectorRepository()
    try:
        query_embedding = await embed_query(query)

        results = await repo.search_chunks(
            knowledge_base_id=knowledge_base_id,
            query_embedding=query_embedding,
            top_k=top_k,
            filter_doc_ids=filter_doc_ids,
        )

        if not results:
            logger.debug("No RAG results for KB %s query: %s", knowledge_base_id, query[:50])
            return None

        return _format_context(results, query, min_score=min_score)

    except Exception as e:
        logger.exception("RAG retrieval failed for KB %s: %s", knowledge_base_id, e)
        return None
