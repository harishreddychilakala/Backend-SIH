"""
BIS SmartAI — Document Service
Manages uploaded documents, PDF processing, semantic chunking, pgvector indexing, and compliance analysis with user isolation.
"""
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
import os
import re
from typing import List, Optional, Dict, Any, Tuple
import psycopg2
import psycopg2.extras
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.document import Document
from app.models.user import User
from app.services.vision_service import vision_service
from app.services.gemini_service import gemini_service
from rag.chunking import chunk_document, DocumentChunk
from rag.embeddings import embedding_service

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    _PYMUPDF_AVAILABLE = True
except ImportError:
    _PYMUPDF_AVAILABLE = False

try:
    import pypdf
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False


def _get_raw_connection():
    """Direct PostgreSQL connection for vector indexing."""
    return psycopg2.connect(
        settings.database_url,
        sslmode="require",
        connect_timeout=15,
    )


def _extract_pages_from_pdf_bytes(pdf_bytes: bytes) -> List[Tuple[int, str]]:
    """
    Extract text page-by-page from PDF bytes.
    Returns list of (page_number, text) tuples (1-indexed).
    """
    pages = []
    if _PYMUPDF_AVAILABLE:
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                text = page.get_text("text")
                if text and text.strip():
                    pages.append((page_idx + 1, text.strip()))
            doc.close()
            if pages:
                return pages
        except Exception as e:
            logger.warning(f"PyMuPDF failed to extract pages: {e}. Trying pypdf fallback.")

    if _PYPDF_AVAILABLE:
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    pages.append((page_idx + 1, text.strip()))
            if pages:
                return pages
        except Exception as e:
            logger.error(f"pypdf failed to extract pages: {e}")

    return pages


def _insert_user_chunks_to_db(
    chunks: List[DocumentChunk],
    doc_id: str,
    user_id: str,
) -> Tuple[int, int]:
    """
    Generate embeddings and insert chunks into document_chunks table.
    """
    if not chunks:
        return 0, 0

    texts = [c.content for c in chunks]
    embeddings = embedding_service.embed_documents(texts)
    inserted = 0
    skipped = 0

    conn = None
    try:
        conn = _get_raw_connection()
        with conn.cursor() as cur:
            insert_sql = """
                INSERT INTO document_chunks
                    (domain, document_name, standard_number, standard_title, section, clause,
                     chunk_index, content, embedding, metadata, page_number, document_hash, chunk_hash)
                VALUES
                    (%(domain)s, %(document_name)s, %(standard_number)s, %(standard_title)s,
                     %(section)s, %(clause)s, %(chunk_index)s, %(content)s,
                     %(embedding)s::vector, %(metadata)s::jsonb,
                     %(page_number)s, %(document_hash)s, %(chunk_hash)s)
                ON CONFLICT (chunk_hash) DO NOTHING
            """
            for chunk, emb in zip(chunks, embeddings):
                if emb is None:
                    skipped += 1
                    continue

                emb_str = f"[{','.join(str(v) for v in emb)}]"
                meta = dict(chunk.metadata)
                meta["is_user_upload"] = True
                meta["user_id"] = user_id
                meta["doc_id"] = doc_id

                params = {
                    "domain": chunk.domain,
                    "document_name": chunk.document_name,
                    "standard_number": chunk.standard_number,
                    "standard_title": chunk.standard_title,
                    "section": chunk.section,
                    "clause": chunk.clause,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "embedding": emb_str,
                    "metadata": json.dumps(meta),
                    "page_number": chunk.page_number,
                    "document_hash": chunk.document_hash,
                    "chunk_hash": chunk.chunk_hash,
                }
                cur.execute(insert_sql, params)
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
        conn.commit()
    except Exception as e:
        logger.error(f"Error inserting user document chunks to database: {e}")
    finally:
        if conn:
            conn.close()

    return inserted, skipped


class DocumentService:
    @staticmethod
    def create_document_analysis(
        db: Session,
        user: User,
        filename: str,
        file_type: str,
        file_bytes: Optional[bytes] = None,
    ) -> Document:
        """
        Record uploaded document metadata, extract text, chunk and embed into pgvector,
        and generate structured AI compliance analysis.
        """
        if not file_bytes or len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty or corrupted. Please upload a valid document or image.",
            )

        # 1. Compute SHA-256 for idempotency & deduplication
        doc_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size_kb = round(len(file_bytes) / 1024, 1)
        file_size_str = f"{file_size_kb} KB" if file_size_kb < 1024 else f"{round(file_size_kb / 1024, 2)} MB"

        is_pdf = file_type == "application/pdf" or filename.lower().endswith(".pdf")
        is_image = file_type.startswith("image/") or any(filename.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"])

        # Create base Document record
        doc = Document(
            user_id=user.id,
            filename=filename,
            file_type=file_type,
            analysis_status="processing",
            analysis_result={},
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        try:
            if is_pdf:
                # ── PDF Processing & RAG Vector Indexing Pipeline ──
                pages = _extract_pages_from_pdf_bytes(file_bytes)
                if not pages:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Could not extract text from this PDF. It may be password-protected, corrupted, or contain scanned images without embedded text.",
                    )

                domain = f"User Upload: {filename}"
                chunks = chunk_document(
                    domain=domain,
                    document_name=filename,
                    pages=pages,
                    document_hash=doc_hash,
                )

                inserted_count, skipped_count = _insert_user_chunks_to_db(
                    chunks=chunks,
                    doc_id=doc.id,
                    user_id=user.id,
                )

                # Generate AI synthesis from extracted text
                sample_text = "\n".join([p[1][:500] for p in pages[:4]])
                analysis_prompt = f"""Analyze this technical document/standard titled '{filename}':
Extracted Sample Text:
{sample_text[:2500]}

Generate a structured JSON analysis object:
{{
  "product_name": "Identified product / system name",
  "category": "Product Category (e.g. Electrical, Steel, Food, Electronics, Safety)",
  "applicable_standard": {{
    "number": "IS number if mentioned or null",
    "title": "Standard Title if mentioned",
    "status": "Active"
  }},
  "summary": "Executive summary of the document (3-4 sentences)",
  "detected_markings": ["Markings / specifications / ratings mentioned in text"],
  "extracted_requirements": [
    {{"text": "Key requirement clause from document", "category": "Safety/Technical"}}
  ],
  "testing_clauses": [
    {{"test_name": "Testing method mentioned", "description": "Brief description"}}
  ],
  "compliance_gaps": [],
  "qco_mandate": {{
    "is_mandatory": false,
    "qco_order_name": "Quality Control Order (verify applicability)",
    "effective_status": "Review Gazette notification"
  }},
  "certification_scheme": {{
    "scheme": "Scheme I (ISI Mark) / Scheme II (CRS)",
    "process": "Standard BIS certification process via Manakonline"
  }}
}}

Return strictly valid JSON."""

                ai_res = gemini_service.generate_response(analysis_prompt)
                ai_res["filename"] = filename
                ai_res["file_size"] = file_size_str
                ai_res["page_count"] = len(pages)
                ai_res["chunks_indexed"] = len(chunks)
                ai_res["rag_indexed"] = True
                ai_res["source_type"] = "User Uploaded Document"
                ai_res["verification_status"] = "user_uploaded_document"
                ai_res["uploaded_at"] = datetime.now(timezone.utc).isoformat()

                doc.analysis_status = "completed"
                doc.analysis_result = ai_res
                db.add(doc)
                db.commit()
                db.refresh(doc)
                return doc

            elif is_image:
                # ── Image / Vision AI Analysis ──
                analysis_result = vision_service.analyze_image_bytes(
                    image_bytes=file_bytes,
                    mime_type=file_type,
                    filename=filename,
                )
                analysis_result["file_size"] = file_size_str
                analysis_result["uploaded_at"] = datetime.now(timezone.utc).isoformat()

                doc.analysis_status = "completed"
                doc.analysis_result = analysis_result
                db.add(doc)
                db.commit()
                db.refresh(doc)
                return doc

            else:
                # Fallback for other file formats
                analysis_result = vision_service._fallback_analysis(filename)
                analysis_result["filename"] = filename
                analysis_result["file_size"] = file_size_str
                analysis_result["uploaded_at"] = datetime.now(timezone.utc).isoformat()

                doc.analysis_status = "completed"
                doc.analysis_result = analysis_result
                db.add(doc)
                db.commit()
                db.refresh(doc)
                return doc

        except HTTPException:
            db.delete(doc)
            db.commit()
            raise
        except Exception as e:
            logger.error(f"Failed to process document '{filename}': {e}")
            doc.analysis_status = "failed"
            doc.analysis_result = {"error": str(e), "filename": filename, "uploaded_at": datetime.now(timezone.utc).isoformat()}
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return doc

    @staticmethod
    def get_user_documents(db: Session, user: User) -> List[Document]:
        """Get documents belonging ONLY to authenticated user."""
        return db.query(Document).filter(
            Document.user_id == user.id
        ).order_by(desc(Document.created_at)).all()

    @staticmethod
    def get_document(db: Session, user: User, doc_id: str) -> Document:
        """Get single document with user isolation."""
        doc = db.query(Document).filter(
            Document.id == doc_id,
            Document.user_id == user.id,
        ).first()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or access denied.",
            )
        return doc

    @staticmethod
    def delete_document(db: Session, user: User, doc_id: str) -> bool:
        """Delete document and its corresponding vector chunks with user isolation."""
        doc = db.query(Document).filter(
            Document.id == doc_id,
            Document.user_id == user.id,
        ).first()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or access denied.",
            )

        # Clean up chunks from document_chunks table if any were indexed
        try:
            conn = _get_raw_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM document_chunks WHERE document_name = %s AND (metadata->>'user_id' = %s OR metadata->>'doc_id' = %s)",
                    (doc.filename, user.id, doc.id)
                )
            conn.commit()
            conn.close()
        except Exception as ce:
            logger.warning(f"Failed to clean up vector chunks for doc {doc.id}: {ce}")

        db.delete(doc)
        db.commit()
        return True

