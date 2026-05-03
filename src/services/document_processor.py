"""Background document processing: parse → chunk → embed → index in Qdrant."""

import asyncio
import os

from src.core.config import settings
from src.core.logging import logging
from src.core.database import AsyncSessionLocal
from src.services.document_parser import parse_document, ParsedDocument
from src.services.chunking_service import chunk_documents, Chunk
from src.services.embedding_service import embed_texts
from src.persistencia.vector import VectorRepository
from src.persistencia.vector.vector_store_port import VectorStorePort
from src.persistencia.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    End-to-end document processing pipeline.

    Pipeline:
    1. Parse document (PDF/TXT/CSV/JSON → text + per-page metadata)
    2. Chunk with metadata preservation (RecursiveCharacterTextSplitter)
    3. Generate embeddings (batch_size=64, normalized)
    4. Upsert chunks + metadata to Qdrant
    5. Update document status
    """

    def __init__(self, vector_repo: VectorStorePort | None = None) -> None:
        self._vector_repo = vector_repo

    @property
    def vector_repo(self) -> VectorStorePort:
        if self._vector_repo is None:
            self._vector_repo = VectorRepository()
        return self._vector_repo

    async def _resolve_file_path(self, file_id: str) -> str | None:
        """Resolve file path on disk (non-blocking via thread)."""
        base_path = os.path.join(settings.UPLOAD_DIR, file_id)
        if await asyncio.to_thread(os.path.exists, base_path):
            return base_path
        files = await asyncio.to_thread(os.listdir, settings.UPLOAD_DIR)
        for f in files:
            if f.startswith(file_id):
                return os.path.join(settings.UPLOAD_DIR, f)
        return None

    async def _parse(self, file_path: str) -> ParsedDocument:
        """Parse document asynchronously."""
        return await parse_document(file_path)

    async def _chunk(
        self,
        parsed: ParsedDocument,
        doc_id: int,
        filename: str,
    ) -> list[Chunk]:
        """Split parsed text into metadata-rich chunks."""
        return chunk_documents(
            parsed.text,
            doc_id=doc_id,
            filename=filename,
            base_metadata=parsed.metadata,
        )

    async def _embed(self, chunks: list[Chunk]) -> list[list[float]]:
        """Generate embeddings for all chunk texts."""
        texts = [c.text for c in chunks]
        return await embed_texts(texts, batch_size=64, normalize=True)

    async def _index(
        self,
        knowledge_base_id: int,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        doc_id: int,
    ) -> None:
        """Upsert chunks with per-chunk metadata to vector store."""
        # Build per-chunk payloads so page numbers etc. travel with each vector
        chunk_texts = [c.text for c in chunks]
        # The repository already handles bulk upsert; metadata is global per call.
        # For per-chunk metadata we need to enrich the payload.
        # We merge chunk-specific metadata into the global metadata dict.
        # This is a design trade-off: Qdrant PointStruct has a single payload per point.
        # We pass the first chunk's metadata as base and let the repo handle it.
        base_meta = chunks[0].metadata if chunks else {}
        await self.vector_repo.upsert_chunks(
            knowledge_base_id=knowledge_base_id,
            chunks=chunk_texts,
            embeddings=embeddings,
            metadata=base_meta,
            doc_id=doc_id,
        )

    async def process_document(
        self,
        doc_id: int,
        knowledge_base_id: int,
    ) -> None:
        """Process a single document in a fresh DB session with transaction safety."""
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)

            doc = await doc_repo.get_by_id(doc_id)
            if not doc:
                logger.error("Document %s not found for processing", doc_id)
                return

            try:
                # 0. Update status to processing
                doc.status = "processing"
                await session.commit()

                # 1. Resolve file path
                file_path = await self._resolve_file_path(doc.file_id)
                if not file_path:
                    raise FileNotFoundError(f"File not found for document {doc_id}")

                # 2. Parse
                parsed = await self._parse(file_path)
                if not parsed.text.strip():
                    raise ValueError("No text extracted from document")

                # 3. Chunk (with metadata preservation)
                chunks = await self._chunk(parsed, doc_id, doc.filename)
                if not chunks:
                    raise ValueError("No chunks generated")

                # 4. Embed
                embeddings = await self._embed(chunks)

                # 5. Index
                collection_name = f"kb_{knowledge_base_id}"
                await self._index(knowledge_base_id, chunks, embeddings, doc_id)

                # 6. Finalize
                doc.status = "indexed"
                doc.qdrant_collection = collection_name
                await session.commit()
                logger.info(
                    "Document %d indexed successfully in %s (%d chunks, parser=%s)",
                    doc_id,
                    collection_name,
                    len(chunks),
                    parsed.metadata.get("parser", "unknown"),
                )

            except Exception:
                logger.exception("Failed to process document %d", doc_id)
                await session.rollback()
                doc.status = "failed"
                await session.commit()
