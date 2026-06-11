"""Text chunking with overlap and contextual enrichment for RAG.

Uses LangChain RecursiveCharacterTextSplitter — the industry-standard default.
Hierarchical separators preserve paragraphs → sentences → words.

Contextual Chunking (Anthropic technique, 2024):
- Prepends a short document-level context to each chunk before embedding.
- Reduces retrieval failure rates by 35% on isolated chunk queries.
- Applied at indexing time (no runtime latency cost).

Layer: services (business logic / domain orchestration)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.core.logging import logging

logger = logging.getLogger(__name__)

# ── Token-based defaults ──
# English ~4 chars/token; Spanish ~3.5 chars/token.  We use a conservative
# 4-char heuristic so 512 chars ≈ 128 tokens — well within all-MiniLM-L6-v2
# context window and leaving headroom for the query + prompt.
DEFAULT_CHUNK_SIZE_CHARS = 1024   # ≈ 256 tokens
DEFAULT_CHUNK_OVERLAP_CHARS = 200  # ≈ 50 tokens  (~20% overlap)

# 5-level hierarchy: paragraph → line → sentence → word → character
# ". " is critical: without it sentences get split mid-thought.
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _make_splitter(
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
    separators: list[str] | None = None,
    length_function: Callable[[str], int] | None = None,
) -> RecursiveCharacterTextSplitter:
    """Factory for a configured text splitter."""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=length_function or len,
        separators=separators or DEFAULT_SEPARATORS,
        is_separator_regex=False,
    )


@dataclass(frozen=True, slots=True)
class Chunk:
    """A text chunk with associated metadata for RAG."""

    text: str
    metadata: dict
    index: int


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """
    Split text into overlapping chunks using RecursiveCharacterTextSplitter.

    Args:
        text: Raw text to split.
        chunk_size: Target chunk length in characters (default 1024 ≈ 256 tokens).
        overlap: Characters to overlap between chunks (default 200 ≈ 20%).

    Returns:
        List of non-empty chunk strings.
    """
    if not text or not text.strip():
        return []

    splitter = _make_splitter(chunk_size, overlap)
    chunks = splitter.split_text(text)
    return [c for c in chunks if c.strip()]


def chunk_documents(
    text: str,
    *,
    doc_id: int | str,
    filename: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
    base_metadata: dict | None = None,
) -> list[Chunk]:
    """
    Split text into overlapping chunks while preserving metadata per chunk.

    Each chunk carries metadata such as chunk index, source filename, and
    optional base metadata (e.g. page_number, total_pages).

    Returns:
        List of Chunk objects ready for embedding + vector upsert.
    """
    if not text or not text.strip():
        return []

    splitter = _make_splitter(chunk_size, overlap)
    chunks = splitter.split_text(text)

    result: list[Chunk] = []
    base = base_metadata or {}
    for i, chunk_text in enumerate(chunks):
        if not chunk_text.strip():
            continue
        meta = {
            **base,
            "chunk_index": i,
            "doc_id": doc_id,
            "filename": filename,
        }
        result.append(Chunk(text=chunk_text, metadata=meta, index=i))

    logger.debug("Split %s into %d chunks (size=%d, overlap=%d)", filename, len(result), chunk_size, overlap)
    return result


# ── Contextual Chunking (Anthropic technique) ──

_CONTEXT_PROMPT = """\
<document>
{doc_summary}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk_text}
</chunk>

Please give a short succinct context (2-3 sentences, max 80 words) to situate \
this chunk within the overall document for the purpose of improving search \
retrieval of the chunk. Answer ONLY with the context, no preamble."""


async def _generate_chunk_context(
    doc_summary: str,
    chunk_text: str,
) -> str:
    """Use the local LLM to generate situating context for a chunk.

    This context is prepended to the chunk before embedding, improving
    retrieval accuracy by 35% (Anthropic Contextual Retrieval, 2024).
    """
    try:
        from backend.ia.llm_client import get_llm_client

        prompt = _CONTEXT_PROMPT.format(
            doc_summary=doc_summary,
            chunk_text=chunk_text[:500],  # Limit chunk preview for efficiency
        )
        client = get_llm_client()
        response = await client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            max_tokens=120,
            temperature=0.3,  # Low temp for factual context generation
        )
        # Parse OpenAI-compatible response format
        choices = response.get("choices", [])
        if choices:
            context = choices[0].get("message", {}).get("content", "").strip()
            return context
        return ""
    except Exception as e:
        logger.warning("Chunk contextualization failed: %s", e)
        return ""


async def contextualize_chunks(
    chunks: list[Chunk],
    full_document_text: str,
    *,
    max_concurrent: int = 5,
) -> list[Chunk]:
    """Prepend document-level context to each chunk (Anthropic technique).

    Uses the local LLM to generate a brief situating summary for each chunk.
    Processes chunks in parallel with bounded concurrency to balance speed
    and resource usage.

    Args:
        chunks: List of Chunk objects from the splitter.
        full_document_text: The full document text (first 4K chars used).
        max_concurrent: Max parallel LLM calls.

    Returns:
        List of Chunk objects with contextualized text.
    """
    if not chunks:
        return chunks

    # Use first 4K chars as document summary for efficiency
    doc_summary = full_document_text[:4000]
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _contextualize_one(chunk: Chunk) -> Chunk:
        async with semaphore:
            context = await _generate_chunk_context(doc_summary, chunk.text)
            if context:
                enriched_text = f"[Context: {context}]\n\n{chunk.text}"
            else:
                enriched_text = chunk.text
            return Chunk(text=enriched_text, metadata=chunk.metadata, index=chunk.index)

    tasks = [asyncio.create_task(_contextualize_one(c)) for c in chunks]
    contextualized = await asyncio.gather(*tasks)

    logger.info(
        "Contextualized %d/%d chunks successfully",
        sum(1 for c in contextualized if c.text.startswith("[Context:")),
        len(chunks),
    )
    return list(contextualized)


def chunk_text_semantic(
    text: str,
    *,
    embed_fn: Callable[[str], list[float]],
    breakpoint_threshold_type: str = "percentile",
    breakpoint_threshold_amount: float = 95.0,
) -> list[str]:
    """
    Semantic chunking: split at topic boundaries using embedding similarity.

    This requires an embedding function (e.g. sentence-transformers) and is
    slower than recursive splitting, but produces higher-quality chunks for
    long documents with distinct sections.

    Args:
        text: Raw text to split.
        embed_fn: Function that takes a string and returns an embedding vector.
        breakpoint_threshold_type: "percentile" | "standard_deviation" | "interquartile".
        breakpoint_threshold_amount: Threshold value (e.g. 95 for percentile).

    Returns:
        List of non-empty chunk strings.
    """
    if not text or not text.strip():
        return []

    try:
        from langchain_experimental.text_splitter import SemanticChunker
    except ImportError:
        logger.warning("langchain_experimental not installed; falling back to recursive chunking")
        return chunk_text(text)

    # Wrap the sync embed_fn in a LangChain-compatible callable
    def _embed(texts: list[str]) -> list[list[float]]:
        return [embed_fn(t) for t in texts]

    splitter = SemanticChunker(
        embeddings=_embed,  # type: ignore[arg-type]
        breakpoint_threshold_type=breakpoint_threshold_type,
        breakpoint_threshold_amount=breakpoint_threshold_amount,
    )
    chunks = splitter.split_text(text)
    return [c for c in chunks if c.strip()]
