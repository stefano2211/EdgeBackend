"""Text chunking with overlap for RAG.

Uses LangChain RecursiveCharacterTextSplitter — the industry-standard default.
Hierarchical separators preserve paragraphs → sentences → words.
Supports semantic chunking (embedding-based) and metadata-preserving chunking.

Layer: services (business logic / domain orchestration)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.logging import logging

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
