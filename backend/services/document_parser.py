"""Extract text from uploaded documents (PDF, TXT, MD, CSV, JSON).

Design:
- Page-aware PDF parsing with fallback backends (pypdf → PyMuPDF).
- Metadata preservation for RAG (page numbers, titles, row counts).
- All sync I/O wrapped via asyncio.to_thread() for non-blocking execution.
- Supports both file paths (legacy) and in-memory bytes (MinIO/S3).
"""

from __future__ import annotations

import asyncio
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from backend.core.logging import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Structured output from document parsing with per-page metadata support."""

    text: str
    metadata: dict = field(default_factory=dict)
    pages: list[dict] = field(default_factory=list)
    """Per-page text/metadata (PDF only). Empty for other formats."""


# ── PDF parsers ──

def _parse_pdf_pypdf_stream(stream: BinaryIO) -> ParsedDocument:
    """Extract text using pypdf from a file-like object."""
    from pypdf import PdfReader
    reader = PdfReader(stream)
    pages: list[dict] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if text:
            pages.append({"page_number": i, "text": text})
    return ParsedDocument(
        text="\n\n".join(p["text"] for p in pages),
        metadata={"total_pages": len(reader.pages), "file_type": "pdf", "parser": "pypdf"},
        pages=pages,
    )


def _parse_pdf_pymupdf_stream(data: bytes) -> ParsedDocument:
    """Extract text using PyMuPDF (fitz) from raw bytes."""
    import fitz  # PyMuPDF
    doc = fitz.open(stream=data, filetype="pdf")
    pages: list[dict] = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        if text:
            pages.append({"page_number": i, "text": text})
    doc.close()
    return ParsedDocument(
        text="\n\n".join(p["text"] for p in pages),
        metadata={"total_pages": len(doc), "file_type": "pdf", "parser": "pymupdf"},
        pages=pages,
    )


def _parse_pdf_bytes(data: bytes, *, filename: str = "") -> ParsedDocument:
    """Extract text from PDF bytes with best-available backend and fallback."""
    try:
        return _parse_pdf_pymupdf_stream(data)
    except Exception:
        logger.warning("PyMuPDF failed for %s, falling back to pypdf", filename)
        return _parse_pdf_pypdf_stream(io.BytesIO(data))




# ── Text / JSON / Markdown parsers ──

def _parse_text_bytes(data: bytes, *, ext: str = ".txt") -> ParsedDocument:
    """Read a plain text / markdown / JSON file from bytes."""
    raw = data.decode("utf-8", errors="ignore")
    text = raw
    metadata: dict = {"file_type": ext.lstrip(".")}

    if ext == ".json":
        try:
            data_obj = json.loads(raw)
            if isinstance(data_obj, dict):
                text = "\n".join(f"{k}: {v}" for k, v in data_obj.items())
            elif isinstance(data_obj, list):
                text = "\n".join(json.dumps(item, ensure_ascii=False) for item in data_obj)
            metadata["json_keys"] = list(data_obj.keys()) if isinstance(data_obj, dict) else None
        except json.JSONDecodeError:
            text = raw  # fallback: treat as plain text

    return ParsedDocument(text=text, metadata=metadata)




# ── CSV parser ──

def _parse_csv_bytes(data: bytes) -> ParsedDocument:
    """Convert CSV rows into a structured text block with headers preserved."""
    import csv
    text_stream = io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="ignore", newline="")
    rows: list[list[str]] = []
    reader = csv.reader(text_stream)
    for row in reader:
        rows.append(row)

    if not rows:
        return ParsedDocument(text="", metadata={"file_type": "csv", "rows": 0})

    header = " | ".join(rows[0])
    data_rows = [" | ".join(row) for row in rows[1:]]
    text = f"HEADER: {header}\n" + "\n".join(data_rows)

    return ParsedDocument(
        text=text,
        metadata={"file_type": "csv", "rows": len(rows), "columns": len(rows[0]) if rows else 0},
    )




# ── Dispatch ──

_PARSER_MAP: dict[str, callable] = {
    ".pdf": _parse_pdf_bytes,
    ".txt": _parse_text_bytes,
    ".md": _parse_text_bytes,
    ".json": _parse_text_bytes,
    ".csv": _parse_csv_bytes,
}


def _resolve_ext(filename: str) -> str:
    """Return lower-case extension from filename."""
    return Path(filename).suffix.lower()


def _resolve_parser(ext: str):
    """Return the sync parser function for a given file extension."""
    return _PARSER_MAP.get(ext, _parse_text_bytes)


# ── Public API ──

async def parse_document_bytes(data: bytes, *, filename: str) -> ParsedDocument:
    """Dispatch to the appropriate parser from in-memory bytes.

    Args:
        data: Raw file bytes (e.g. downloaded from MinIO/S3).
        filename: Original filename — used to infer file type.

    Returns:
        ParsedDocument with extracted text and metadata.
    """
    ext = _resolve_ext(filename)
    bytes_parser = _resolve_parser(ext)

    if ext == ".pdf":
        # PDF parser needs filename for fallback logging
        return await asyncio.to_thread(bytes_parser, data, filename=filename)
    elif ext in (".txt", ".md", ".json"):
        return await asyncio.to_thread(bytes_parser, data, ext=ext)
    else:
        return await asyncio.to_thread(bytes_parser, data)
