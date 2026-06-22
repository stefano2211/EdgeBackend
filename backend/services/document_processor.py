"""Background document processing: download → parse → chunk → contextualize → embed → index.

Full 2026 RAG ingestion pipeline:
1. Download bytes from MinIO/S3
2. Parse document bytes (PDF/TXT/CSV/JSON → text + per-page metadata)
3. Chunk with metadata preservation (RecursiveCharacterTextSplitter)
4. Contextualize chunks (Anthropic technique — LLM-generated context per chunk)
5. Generate dense embeddings (all-MiniLM-L6-v2, batch_size=64, normalized)
6. Generate sparse embeddings (BM25 via fastembed)
7. Upsert dual vectors + metadata to Qdrant (named vectors: dense + sparse)
8. Update document status in PostgreSQL
"""

from __future__ import annotations

from backend.core.config import settings
from backend.core.logging import logging
from backend.core.database import AsyncSessionLocal
from backend.application.knowledge.parser import parse_document_bytes, ParsedDocument
from backend.application.knowledge.chunking import chunk_documents, contextualize_chunks, Chunk
from backend.infrastructure.embeddings.dense import embed_texts
from backend.persistencia.vector import VectorRepository
from backend.infrastructure.vector.vector_store_port import VectorStorePort, SparseVector
from backend.infrastructure.persistence.document_repository import DocumentRepository
from backend.infrastructure.storage.storage_port import StoragePort

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    End-to-end document processing pipeline.

    Pipeline:
    1. Download bytes from MinIO/S3 (file_id is the full S3 key)
    2. Parse document bytes (PDF/TXT/CSV/JSON → text + per-page metadata)
    3. Chunk with metadata preservation (RecursiveCharacterTextSplitter)
    4. Contextualize chunks (Anthropic technique — optional, LLM-generated)
    5. Generate dense embeddings (batch_size=64, normalized)
    6. Generate sparse BM25 embeddings (fastembed)
    7. Upsert dual vectors + metadata to Qdrant
    8. Update document status
    """

    def __init__(
        self,
        vector_repo: VectorStorePort | None = None,
        storage: StoragePort | None = None,
    ) -> None:
        self._vector_repo = vector_repo
        self._storage = storage

    @property
    def vector_repo(self) -> VectorStorePort:
        if self._vector_repo is None:
            self._vector_repo = VectorRepository()
        return self._vector_repo

    async def _download(self, s3_key: str) -> bytes:
        """Download document bytes from object storage."""
        if self._storage is None:
            from backend.persistencia.storage import MinioStorageRepository
            self._storage = MinioStorageRepository()
        return await self._storage.download(s3_key)

    async def _parse(self, data: bytes, filename: str) -> ParsedDocument:
        """Parse document bytes asynchronously."""
        return await parse_document_bytes(data, filename=filename)

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

    async def _contextualize(
        self, chunks: list[Chunk], full_text: str
    ) -> list[Chunk]:
        """Apply Anthropic contextual chunking if enabled.

        Prepends a short LLM-generated context to each chunk to improve
        retrieval accuracy by ~35%.
        """
        if not settings.CONTEXTUAL_CHUNKING_ENABLED:
            logger.debug("Contextual chunking disabled, skipping")
            return chunks

        try:
            return await contextualize_chunks(chunks, full_text)
        except Exception as e:
            logger.warning("Contextual chunking failed, using raw chunks: %s", e)
            return chunks

    async def _embed_dense(self, chunks: list[Chunk]) -> list[list[float]]:
        """Generate dense embeddings for all chunk texts."""
        texts = [c.text for c in chunks]
        return await embed_texts(texts, batch_size=64, normalize=True)

    async def _embed_sparse(self, chunks: list[Chunk]) -> list[SparseVector] | None:
        """Generate sparse BM25 embeddings for all chunk texts.

        Returns None if hybrid search is disabled or fastembed unavailable.
        """
        if not settings.HYBRID_SEARCH_ENABLED:
            return None

        try:
            from backend.infrastructure.embeddings.sparse import embed_sparse_texts

            texts = [c.text for c in chunks]
            return await embed_sparse_texts(texts)
        except ImportError:
            logger.warning("fastembed not available; skipping sparse embeddings")
            return None
        except Exception as e:
            logger.warning("Sparse embedding failed: %s", e)
            return None

    async def _index(
        self,
        knowledge_base_id: int,
        chunks: list[Chunk],
        dense_embeddings: list[list[float]],
        sparse_embeddings: list[SparseVector] | None,
        doc_id: int,
        context: list[str] | None = None,
    ) -> None:
        """Upsert chunks with dual vectors (dense + sparse) to vector store."""
        chunk_texts = [c.text for c in chunks]
        # Each chunk carries its own metadata (chunk_index, filename, page_number, etc.)
        meta_list = [c.metadata for c in chunks]
        await self.vector_repo.upsert_chunks(
            knowledge_base_id=knowledge_base_id,
            chunks=chunk_texts,
            embeddings=dense_embeddings,
            metadata=meta_list,
            doc_id=doc_id,
            sparse_embeddings=sparse_embeddings,
            context=context,
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

                # Determine which contexts this KB serves
                from backend.infrastructure.persistence.knowledge_repository import KnowledgeRepository
                kb_repo = KnowledgeRepository(session)
                kb = await kb_repo.get_by_id(knowledge_base_id)
                contexts = []
                if kb and kb.is_enabled_chat:
                    contexts.append("chat")
                if kb and kb.is_enabled_reactive:
                    contexts.append("reactive")

                # 1. Download from MinIO/S3 (file_id is the full S3 key)
                data = await self._download(doc.file_id)
                if not data:
                    raise ValueError(f"Empty file downloaded for document {doc_id}")

                # 2. Parse
                parsed = await self._parse(data, doc.filename)
                if not parsed.text.strip():
                    raise ValueError("No text extracted from document")

                # 3. Chunk (with metadata preservation)
                chunks = await self._chunk(parsed, doc_id, doc.filename)
                if not chunks:
                    raise ValueError("No chunks generated")

                # 4. Contextualize (Anthropic technique — optional)
                chunks = await self._contextualize(chunks, parsed.text)

                # 5. Embed (dense — all-MiniLM-L6-v2)
                dense_embeddings = await self._embed_dense(chunks)

                # 6. Embed (sparse — BM25 via fastembed)
                sparse_embeddings = await self._embed_sparse(chunks)

                # 7. Index (dual vectors to Qdrant)
                collection_name = f"kb_{knowledge_base_id}"
                await self._index(
                    knowledge_base_id, chunks, dense_embeddings,
                    sparse_embeddings, doc_id,
                    context=contexts or None,
                )

                # 8. Finalize
                doc.status = "indexed"
                doc.qdrant_collection = collection_name
                await session.commit()
                logger.info(
                    "Document %d indexed successfully in %s "
                    "(%d chunks, parser=%s, contextual=%s, sparse=%s)",
                    doc_id,
                    collection_name,
                    len(chunks),
                    parsed.metadata.get("parser", "unknown"),
                    settings.CONTEXTUAL_CHUNKING_ENABLED,
                    sparse_embeddings is not None,
                )

            except Exception:
                logger.exception("Failed to process document %d", doc_id)
                await session.rollback()
                doc.status = "failed"
                await session.commit()
