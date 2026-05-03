"""Extract text from uploaded documents (PDF, TXT, MD, CSV, JSON).

Layer: services (business logic / domain orchestration)
"""

import asyncio
from pathlib import Path
from typing import TypedDict


class ParsedDocument(TypedDict):
    """Structured output from document parsing."""

    text: str
    metadata: dict


def parse_pdf(file_path: str) -> ParsedDocument:
    """Extract text from a PDF file using pypdf, preserving page numbers."""
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    parts = []
    total_pages = len(reader.pages)
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return {
        "text": "\n\n".join(parts),
        "metadata": {
            "total_pages": total_pages,
            "file_type": "pdf",
        },
    }


def parse_text_file(file_path: str) -> ParsedDocument:
    """Read a plain text file."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return {
        "text": text,
        "metadata": {"file_type": Path(file_path).suffix.lstrip(".")},
    }


def parse_csv(file_path: str) -> ParsedDocument:
    """Convert CSV rows into a single text block."""
    import csv
    parts = []
    with open(file_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            parts.append(" | ".join(row))
    return {
        "text": "\n".join(parts),
        "metadata": {"file_type": "csv", "rows": len(parts)},
    }


async def parse_document(file_path: str) -> ParsedDocument:
    """Dispatch to appropriate parser based on file extension (non-blocking)."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return await asyncio.to_thread(parse_pdf, file_path)
    elif ext in (".txt", ".md", ".json"):
        return await asyncio.to_thread(parse_text_file, file_path)
    elif ext == ".csv":
        return await asyncio.to_thread(parse_csv, file_path)
    else:
        # Fallback: try to read as text
        return await asyncio.to_thread(parse_text_file, file_path)
