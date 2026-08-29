#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BIS SmartAI — PDF Ingestion Pipeline
Processes BIS knowledge domain PDFs and stores chunks + embeddings in Neon PostgreSQL.

Usage:
    python ingestion/ingest_documents.py
    python ingestion/ingest_documents.py --rebuild     # Delete all data and reprocess

The script:
1. Discovers PDFs in backend/data/
2. Hashes each PDF for idempotency
3. Extracts text page-by-page using PyMuPDF
4. Creates BIS-aware semantic chunks
5. Generates embeddings via Google gemini-embedding-001 (768 dims)
6. Inserts into Neon (skips unchanged documents)
7. Verifies the final counts per domain
"""
import os
import sys
import hashlib
import logging
import argparse
import time
from pathlib import Path
from typing import List, Optional, Dict, Tuple

# ── Python path setup ─────────────────────────────────────────────────────────
# Allow running from backend/ directory: python ingestion/ingest_documents.py
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# ── Env loading (before importing settings) ───────────────────────────────────
from dotenv import load_dotenv
load_dotenv(BACKEND_ROOT / ".env")

# ── Now import project modules ────────────────────────────────────────────────
from app.core.config import settings
from rag.embeddings import embedding_service, EMBEDDING_DIMENSION
from rag.chunking import chunk_document, DocumentChunk

import psycopg2
import psycopg2.extras

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24 — new import name
except ImportError:
    try:
        import fitz  # PyMuPDF <= 1.23 fallback
    except ImportError:
        print("PyMuPDF not installed. Run: pip install pymupdf")
        sys.exit(1)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest")

# ── Domain mapping ────────────────────────────────────────────────────────────
# Maps actual filename patterns → domain labels
# Inspect backend/data/ directory for actual filenames before modifying this map.
DOMAIN_MAP: Dict[str, str] = {
    "ELECTRICAL": "Electrical",
    "FOOD": "Food & Agriculture",
    "AGRICULTURE": "Food & Agriculture",
    "HOUSEHOLD": "Household Appliances",
    "APPLIANCE": "Household Appliances",
    "IRON": "Iron & Steel",
    "STEEL": "Iron & Steel",
    "TEXTILE": "Textile & Leather",
    "LEATHER": "Textile & Leather",
}

DATA_DIR = BACKEND_ROOT / "data"


def _hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file for idempotency."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _detect_domain(filename: str) -> str:
    """Map a filename to a domain label using the DOMAIN_MAP."""
    upper = filename.upper()
    for key, domain in DOMAIN_MAP.items():
        if key in upper:
            return domain
    # Default: use filename stem as domain
    return Path(filename).stem.replace("_", " ").title()


def _extract_pages(pdf_path: Path) -> List[Tuple[int, str]]:
    """
    Extract text from every page of a PDF using PyMuPDF.
    Returns list of (page_number, text) tuples (1-indexed).
    Skips blank pages silently.
    """
    pages = []
    try:
        doc = fitz.open(str(pdf_path))
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text("text")
            if text and text.strip():
                pages.append((page_idx + 1, text))
        doc.close()
        logger.info(f"  Extracted {len(pages)} non-empty pages from {pdf_path.name}")
    except Exception as e:
        logger.error(f"  Failed to extract pages from {pdf_path.name}: {e}")
    return pages


def _get_connection():
    """Raw psycopg2 connection to Neon."""
    return psycopg2.connect(
        settings.database_url,
        sslmode="require",
        connect_timeout=30,
    )


def _ensure_schema(conn):
    """Ensure pgvector extension and document_chunks table exist."""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id              BIGSERIAL PRIMARY KEY,
                domain          VARCHAR(100)    NOT NULL,
                document_name   TEXT            NOT NULL,
                standard_number TEXT,
                standard_title  TEXT,
                section         TEXT,
                clause          TEXT,
                chunk_index     INTEGER         NOT NULL,
                content         TEXT            NOT NULL,
                embedding       VECTOR({EMBEDDING_DIMENSION}),
                metadata        JSONB,
                page_number     INTEGER,
                document_hash   VARCHAR(64),
                chunk_hash      VARCHAR(64)     UNIQUE,
                created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx
            ON document_chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS document_chunks_domain_idx ON document_chunks(domain)")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS document_chunks_standard_idx
            ON document_chunks(standard_number) WHERE standard_number IS NOT NULL
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS document_chunks_document_idx ON document_chunks(document_name)")
    conn.commit()
    logger.info("✅ Schema verified (pgvector + document_chunks table + indexes)")


def _document_already_indexed(conn, document_hash: str) -> bool:
    """Check if a document with this hash is already fully indexed."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM document_chunks WHERE document_hash = %s AND embedding IS NOT NULL",
            (document_hash,)
        )
        count = cur.fetchone()[0]
    return count > 0


def _delete_document_chunks(conn, document_name: str):
    """Delete all chunks for a document (used with --rebuild or re-ingestion)."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM document_chunks WHERE document_name = %s", (document_name,))
    conn.commit()
    logger.info(f"  Deleted existing chunks for: {document_name}")


def _insert_chunks_with_embeddings(
    conn,
    chunks: List[DocumentChunk],
    embeddings: List[Optional[List[float]]],
) -> Tuple[int, int]:
    """
    Batch-insert chunks + embeddings into document_chunks.
    Skips chunks with NULL embeddings or conflicting chunk_hash (idempotent).
    Returns (inserted_count, skipped_count).
    """
    inserted = 0
    skipped = 0

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

    import json

    with conn.cursor() as cur:
        for chunk, emb in zip(chunks, embeddings):
            if emb is None:
                skipped += 1
                continue

            emb_str = f"[{','.join(str(v) for v in emb)}]"
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
                "metadata": json.dumps(chunk.metadata),
                "page_number": chunk.page_number,
                "document_hash": chunk.document_hash,
                "chunk_hash": chunk.chunk_hash,
            }
            try:
                cur.execute(insert_sql, params)
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1  # ON CONFLICT DO NOTHING
            except Exception as e:
                logger.error(f"  Insert error for chunk {chunk.chunk_index}: {e}")
                skipped += 1

    conn.commit()
    return inserted, skipped


def _print_sample_chunks(chunks: List[DocumentChunk], n: int = 3):
    """Print first N chunks for visual validation."""
    print(f"\n  Sample chunks (first {min(n, len(chunks))}):")
    for chunk in chunks[:n]:
        print(f"  ├─ Chunk {chunk.chunk_index}")
        print(f"  │  Domain    : {chunk.domain}")
        print(f"  │  Page      : {chunk.page_number}")
        print(f"  │  Standard  : {chunk.standard_number or '—'}")
        print(f"  │  Section   : {chunk.section or '—'}")
        print(f"  │  Clause    : {chunk.clause or '—'}")
        print(f"  │  Content   : {chunk.content[:200].replace(chr(10), ' ')}...")
        print()


def _verify_ingestion(conn) -> Dict[str, int]:
    """Return chunk counts per domain after ingestion."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT domain, COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL GROUP BY domain ORDER BY domain"
        )
        rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}


def process_pdf(
    pdf_path: Path,
    conn,
    rebuild: bool = False,
) -> Dict[str, int]:
    """
    Full pipeline for one PDF:
    1. Hash → idempotency check
    2. Extract pages
    3. BIS-aware chunking
    4. Embedding generation
    5. Insert to Neon
    Returns stats dict.
    """
    filename = pdf_path.name
    domain = _detect_domain(filename)

    print(f"\n{'='*60}")
    print(f"📄 Document  : {filename}")
    print(f"🏷  Domain    : {domain}")
    print(f"{'='*60}")

    # 1. Hash for idempotency
    logger.info("  Computing document hash...")
    doc_hash = _hash_file(pdf_path)
    logger.info(f"  Document hash: {doc_hash[:16]}...")

    # 2. Idempotency check
    if not rebuild and _document_already_indexed(conn, doc_hash):
        logger.info(f"  ✅ Already indexed with same hash — skipping (use --rebuild to force)")
        return {"skipped": True}

    # 3. Delete existing chunks if rebuilding or re-ingesting
    _delete_document_chunks(conn, filename)

    # 4. Extract pages
    logger.info("  Extracting pages...")
    pages = _extract_pages(pdf_path)
    if not pages:
        logger.error(f"  ❌ No text extracted from {filename}. Skipping.")
        return {"error": "no_text_extracted"}

    print(f"  Pages processed : {len(pages)}")

    # 5. BIS-aware chunking
    logger.info("  Chunking...")
    chunks = chunk_document(
        domain=domain,
        document_name=filename,
        pages=pages,
        document_hash=doc_hash,
    )
    print(f"  Chunks created  : {len(chunks)}")

    if not chunks:
        logger.warning(f"  No valid chunks produced from {filename}.")
        return {"chunks": 0}

    # Print sample chunks
    _print_sample_chunks(chunks, n=2)

    # 6. Generate embeddings
    logger.info(f"  Generating {len(chunks)} embeddings...")
    if not embedding_service.is_ready:
        logger.error("  ❌ Embedding service not ready. Check GEMINI_API_KEY in .env")
        return {"error": "embedding_service_not_ready"}

    texts = [chunk.content for chunk in chunks]
    embeddings = embedding_service.embed_documents(texts)

    valid_embs = sum(1 for e in embeddings if e is not None)
    logger.info(f"  Embeddings OK   : {valid_embs}/{len(chunks)}")

    if valid_embs == 0:
        logger.error("  ❌ Zero embeddings generated. Aborting insert for this document.")
        return {"error": "no_embeddings_generated"}

    # 7. Insert to Neon
    logger.info("  Inserting into Neon...")
    inserted, skipped = _insert_chunks_with_embeddings(conn, chunks, embeddings)

    print(f"  ✅ Inserted      : {inserted}")
    if skipped > 0:
        print(f"  ⚠  Skipped       : {skipped} (no embedding or duplicate)")

    return {
        "domain": domain,
        "pages": len(pages),
        "chunks_created": len(chunks),
        "chunks_inserted": inserted,
        "chunks_skipped": skipped,
        "embeddings_ok": valid_embs,
    }


def main():
    parser = argparse.ArgumentParser(
        description="BIS SmartAI — Ingest PDFs into Neon PostgreSQL + pgvector"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete all existing chunk data and re-ingest from scratch.",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process only a specific PDF filename (e.g. 'ELECTRICAL data set.pdf').",
    )
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  BIS SmartAI — PDF Ingestion Pipeline")
    print("="*60)
    print(f"  Data directory  : {DATA_DIR}")
    print(f"  Rebuild mode    : {'YES — deleting all existing data' if args.rebuild else 'NO — idempotent (skip unchanged)'}")
    print(f"  Embedding model : text-embedding-004 ({EMBEDDING_DIMENSION} dims)")
    print("="*60)

    # Verify required config
    if not settings.is_db_configured:
        print("ERROR: DATABASE_URL not configured. Add it to backend/.env")
        sys.exit(1)

    if not settings.is_gemini_configured:
        print("ERROR: GEMINI_API_KEY not configured. Embeddings require a Gemini key.")
        print("Add GEMINI_API_KEY to backend/.env")
        sys.exit(1)

    # Verify embedding service
    if not embedding_service.is_ready:
        print("ERROR: Embedding service failed to initialize. Check GEMINI_API_KEY.")
        sys.exit(1)

    # Discover PDFs
    if args.file:
        pdf_files = [DATA_DIR / args.file]
        if not pdf_files[0].exists():
            print(f"❌ File not found: {pdf_files[0]}")
            sys.exit(1)
    else:
        pdf_files = sorted(DATA_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"❌ No PDF files found in {DATA_DIR}")
        sys.exit(1)

    print(f"\n  Found {len(pdf_files)} PDF(s):")
    for p in pdf_files:
        print(f"    • {p.name}  ({p.stat().st_size / 1024 / 1024:.1f} MB)")

    # Connect to Neon
    print("\n  Connecting to Neon PostgreSQL...")
    try:
        conn = _get_connection()
        conn.autocommit = False
        print("  ✅ Connected.")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    # Ensure schema
    _ensure_schema(conn)

    # Optionally wipe everything
    if args.rebuild:
        print("\n  ⚠  --rebuild: Deleting ALL existing document_chunks data...")
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_chunks")
        conn.commit()
        print("  Done.")

    # Process each PDF
    all_stats = []
    start_time = time.time()

    for pdf_path in pdf_files:
        if not pdf_path.exists():
            print(f"  ⚠  File not found: {pdf_path.name} — skipping.")
            continue
        try:
            stats = process_pdf(pdf_path, conn, rebuild=args.rebuild)
            stats["filename"] = pdf_path.name
            all_stats.append(stats)
        except Exception as e:
            logger.error(f"Unexpected error processing {pdf_path.name}: {e}", exc_info=True)

    # Final verification
    print("\n" + "="*60)
    print("  FINAL VERIFICATION — Neon document_chunks counts per domain")
    print("="*60)
    domain_counts = _verify_ingestion(conn)
    if domain_counts:
        total = sum(domain_counts.values())
        for domain, count in domain_counts.items():
            print(f"  {domain:<30} : {count:>5} chunks")
        print(f"  {'TOTAL':<30} : {total:>5} chunks")
    else:
        print("  ⚠  No chunks found in database (check GEMINI_API_KEY and re-run).")

    elapsed = time.time() - start_time
    print(f"\n  ✅ Ingestion complete in {elapsed:.1f}s")

    conn.close()


if __name__ == "__main__":
    main()
