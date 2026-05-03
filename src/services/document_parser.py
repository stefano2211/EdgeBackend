"""Extract text from uploaded documents (PDF, TXT, MD, CSV, JSON).

Design:
- Page-aware PDF parsing with fallback backends (pypdf → PyMuPDF).
- Metadata preservation for RAG (page numbers, titles, row counts).
- All sync I/O wrapped via asyncio.to_thread() for non-blocking execution.
"""

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

from src.core.logging import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Structured output from document parsing with per-page metadata support."""

    text: str
    metadata: dict = field(default_factory=dict)
    pages: list[dict] = field(default_factory=list)
    """Per-page text/metadata (PDF only). Empty for other formats."""


def _parse_pdf_pypdf(file_path: str) -> ParsedDocument:
    """Extract text using pypdf (pure Python, no extra deps)."""
    from pypdf import PdfReader
    reader = PdfReader(file_path)
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


def _parse_pdf_pymupdf(file_path: str) -> ParsedDocument:
    """Extract text using PyMuPDF (fitz) — higher quality, preserves layout."""
    import fitz  # PyMuPDF
    doc = fitz.open(file_path)
    pages: list[dict] = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        if text:
            pages.append({"page_number": i, "text": text})
    return ParsedDocument(
        text="\n\n".join(p["text"] for p in pages),
        metadata={"total_pages": len(doc), "file_type": "pdf", "parser": "pymupdf"},
        pages=pages,
    )


def parse_pdf(file_path: str) -> ParsedDocument:
    """Extract text from PDF with best-available backend and fallback."""
    try:
        return _parse_pdf_pymupdf(file_path)
    except Exception:
        logger.warning("PyMuPDF failed for %s, falling back to pypdf", Path(file_path).name)
        return _parse_pdf_pypdf(file_path)


def parse_text_file(file_path: str) -> ParsedDocument:
    """Read a plain text / markdown / JSON file."""
    path = Path(file_path)
    ext = path.suffix.lower()
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    text = raw
    metadata: dict = {"file_type": ext.lstrip(".")}

    if ext == ".json":
        try:
            data = json.loads(raw)
            # Flatten common JSON shapes into text
            if isinstance(data, dict):
                text = "\n".join(f"{k}: {v}" for k, v in data.items())
            elif isinstance(data, list):
                text = "\n".join(json.dumps(item, ensure_ascii=False) for item in data)
            metadata["json_keys"] = list(data.keys()) if isinstance(data, dict) else None
        except json.JSONDecodeError:
            text = raw  # fallback: treat as plain text

    return ParsedDocument(text=text, metadata=metadata)


def parse_csv(file_path: str) -> ParsedDocument:
    """Convert CSV rows into a structured text block with headers preserved."""
    import csv
    rows: list[list[str]] = []
    with open(file_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
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


def _resolve_parser(ext: str):
    """Return the sync parser function for a given file extension."""
    ext_map = {
        ".pdf": parse_pdf,
        ".txt": parse_text_file,
        ".md": parse_text_file,
        ".json": parse_text_file,
        ".csv": parse_csv,
    }
    return ext_map.get(ext, parse_text_file)


async def parse_document(file_path: str) -> ParsedDocument:
    """Dispatch to the appropriate parser (non-blocking via thread pool)."""
    ext = Path(file_path).suffix.lower()
    parser = _resolve_parser(ext)
    return await asyncio.to_thread(parser, file_path)
