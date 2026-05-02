"""Background document processing: parse → chunk → embed → index in Qdrant."""

import os

from src.core.config import settings
from src.core.logging import logging
from src.core.database import AsyncSessionLocal
from src.services.document_parser import parse_document
from src.services.chunking_service import chunk_text
from src.services.embedding_service import embed_texts
from src.persistencia.vector import VectorRepository
from src.services.knowledge_service import KnowledgeService
from src.persistencia.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Processes uploaded documents asynchronously.

    Pipeline:
    1. Parse document (PDF/TXT → raw text + metadata)
    2. Chunk text (RecursiveCharacterTextSplitter, 512 chars, ~200 tokens)
    3. Generate embeddings (batch_size=64, normalized)
    4. Upsert chunks to Qdrant via VectorRepository
    5. Update document status to "indexed"
    """

    async def process_document(
        self,
        doc_id: int,
        knowledge_base_id: int,
    ) -> None:
        """Process a single document in a fresh DB session."""
        async with AsyncSessionLocal() as session:
            try:
                doc_repo = DocumentRepository(session)
                kb_service = KnowledgeService(session)
                vector_repo = VectorRepository()

                doc = await doc_repo.get_by_id(doc_id)
                if not doc:
                    logger.error("Document %s not found for processing", doc_id)
                    return

                # Update status to processing
                doc.status = "processing"
                await session.commit()

                # Resolve file path
                file_path = os.path.join(settings.UPLOAD_DIR, f"{doc.file_id}")
                if not os.path.exists(file_path):
                    for f in os.listdir(settings.UPLOAD_DIR):
                        if f.startswith(doc.file_id):
                            file_path = os.path.join(settings.UPLOAD_DIR, f)
                            break

                # 1. Parse (returns dict with text + metadata)
                parsed = await parse_document(file_path)
                raw_text = parsed["text"]
                parse_meta = parsed["metadata"]
                if not raw_text.strip():
                    raise ValueError("No text extracted from document")

                # 2. Chunk (uses RecursiveCharacterTextSplitter defaults)
                chunks = chunk_text(raw_text)
                if not chunks:
                    raise ValueError("No chunks generated")

                # 3. Embed (batch_size=64, normalized for cosine similarity)
                embeddings = await embed_texts(chunks, batch_size=64, normalize=True)

                # 4. Upsert to Qdrant via repository
                collection_name = f"kb_{knowledge_base_id}"
                await vector_repo.upsert_chunks(
                    knowledge_base_id=knowledge_base_id,
                    chunks=chunks,
                    embeddings=embeddings,
                    metadata={
                        "filename": doc.filename,
                        "knowledge_base_id": knowledge_base_id,
                        "total_pages": parse_meta.get("total_pages"),
                    },
                    doc_id=doc_id,
                )

                # 5. Update status
                doc.status = "indexed"
                doc.qdrant_collection = collection_name
                await session.commit()
                logger.info(
                    "Document %d indexed successfully in %s (%d chunks)",
                    doc_id,
                    collection_name,
                    len(chunks),
                )

            except Exception as e:
                logger.exception("Failed to process document %d: %s", doc_id, e)
                async with AsyncSessionLocal() as fail_session:
                    doc_repo = DocumentRepository(fail_session)
                    doc = await doc_repo.get_by_id(doc_id)
                    if doc:
                        doc.status = "failed"
                        await fail_session.commit()
