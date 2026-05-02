"""Text chunking with overlap for RAG.

Uses LangChain RecursiveCharacterTextSplitter — the industry-standard default.
Hierarchical separators preserve paragraphs → sentences → words.

Layer: services (business logic / domain orchestration)
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Default 512-char chunks ≈ 200 tokens for all-MiniLM-L6-v2.
# Overlap 50 chars ≈ 10% (mitigates boundary context loss).
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50

# 5-level hierarchy: paragraph → line → sentence → word → character
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


_splitter = RecursiveCharacterTextSplitter(
    chunk_size=DEFAULT_CHUNK_SIZE,
    chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    length_function=len,
    separators=DEFAULT_SEPARATORS,
    is_separator_regex=False,
)


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """
    Split text into overlapping chunks using RecursiveCharacterTextSplitter.

    Args:
        text: Raw text to split.
        chunk_size: Target chunk length in characters (~200-250 tokens).
        overlap: Characters to overlap between chunks (context continuity).

    Returns:
        List of non-empty chunk strings.
    """
    if not text:
        return []

    splitter = _splitter
    if chunk_size != DEFAULT_CHUNK_SIZE or overlap != DEFAULT_CHUNK_OVERLAP:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            length_function=len,
            separators=DEFAULT_SEPARATORS,
            is_separator_regex=False,
        )

    return [chunk for chunk in splitter.split_text(text) if chunk.strip()]
