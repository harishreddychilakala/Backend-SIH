-- BIS SmartAI — RAG Migration 001
-- Enable pgvector and create document_chunks table
-- Vector dimension: 768 (Google text-embedding-004)
-- Run this manually if not using Alembic:
--   psql $DATABASE_URL -f migrations/001_create_rag_tables.sql

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Document chunks table for RAG retrieval
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
    embedding       VECTOR(768),            -- Google text-embedding-004 = 768 dims
    metadata        JSONB,
    page_number     INTEGER,
    document_hash   VARCHAR(64),            -- SHA-256 of full document content
    chunk_hash      VARCHAR(64)     UNIQUE, -- SHA-256 of chunk content (idempotency key)
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- HNSW index for fast approximate nearest-neighbour cosine similarity
CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx
ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Filtered retrieval indexes
CREATE INDEX IF NOT EXISTS document_chunks_domain_idx
ON document_chunks(domain);

CREATE INDEX IF NOT EXISTS document_chunks_standard_idx
ON document_chunks(standard_number)
WHERE standard_number IS NOT NULL;

CREATE INDEX IF NOT EXISTS document_chunks_document_idx
ON document_chunks(document_name);

CREATE INDEX IF NOT EXISTS document_chunks_section_idx
ON document_chunks(section)
WHERE section IS NOT NULL;

CREATE INDEX IF NOT EXISTS document_chunks_doc_hash_idx
ON document_chunks(document_hash)
WHERE document_hash IS NOT NULL;

-- Verification queries
-- SELECT COUNT(*) FROM document_chunks;
-- SELECT domain, COUNT(*) as chunks FROM document_chunks GROUP BY domain ORDER BY domain;
-- SELECT domain, COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embeddings FROM document_chunks GROUP BY domain;
