"""RAG tool — real document retrieval from Qdrant.

Orchestrates: embed query → search vectors → format context for LLM.
"""

from src.core.logging import logging
from src.services.embedding_service import embed_query
from src.persistencia.vector import VectorRepository
from src.persistencia.vector.vector_store_port import VectorStorePort

logger = logging.getLogger(__name__)


async def rag_retrieve(
    knowledge_base_id: str,
    query: str,
    top_k: int = 5,
    filter_doc_ids: list[int | str] | None = None,
    vector_repo: VectorStorePort | None = None,
) -> str | None:
    """
    Search Qdrant for relevant document chunks and return formatted context.

    Returns None if no knowledge base or no results.
    Never raises — returns None on any error to avoid breaking the chat.
    """
    repo = vector_repo if vector_repo is not None else VectorRepository()
    try:
        # Embed the query
        query_embedding = await embed_query(query)

        # Search vectors via repository
        results = await repo.search_chunks(
            knowledge_base_id=knowledge_base_id,
            query_embedding=query_embedding,
            top_k=top_k,
            filter_doc_ids=filter_doc_ids,
        )

        if not results:
            logger.debug(
                "No RAG results for KB %s query: %s",
                knowledge_base_id,
                query[:50],
            )
            return None

        # Format context with structured <source> tags for LLM
        sources = []
        for r in results:
            filename = r.get("filename") or "unknown"
            page = r.get("page_number")
            page_attr = f' page="{page}"' if page else ""
            sources.append(
                f'<source doc="{filename}" chunk="{r["chunk_index"]}"{page_attr}>\n'
                f"{r['text']}\n"
                f"</source>"
            )

        context = "\n\n".join(sources)

        # Wrap with instruction so the LLM knows how to use the context
        return (
            "Use the following sources to answer the question. "
            "If the answer is not found in the sources, say you do not know.\n\n"
            f"{context}\n\n"
            f"Question: {query}"
        )

    except Exception as e:
        logger.exception("RAG retrieval failed for KB %s: %s", knowledge_base_id, e)
        return None
