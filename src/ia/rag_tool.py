"""RAG tool — stub for document retrieval from Qdrant.

Fase 6: stub that returns placeholder context.
Fase 7: real implementation with chunking, embedding, and Qdrant search.
"""


async def rag_retrieve(knowledge_base_id: str, query: str, top_k: int = 5) -> str | None:
    """
    Search Qdrant for relevant document chunks and return concatenated context.

    Returns None if no knowledge base or no results.
    """
    # Stub: simulate retrieval
    # In Fase 7:
    # 1. Load document chunks from Qdrant collection for this knowledge_base_id
    # 2. Embed query using sentence-transformers
    # 3. Vector search top_k nearest chunks
    # 4. Concatenate and return as context string
    return None  # Return None for now — no context injection
