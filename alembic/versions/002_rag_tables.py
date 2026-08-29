"""RAG document_chunks table with pgvector support

Revision ID: 002_rag_tables
Revises: 001_initial
Create Date: 2026-08-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '002_rag_tables'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create document_chunks table
    # VECTOR(768) matches Google text-embedding-004 output dimension
    op.execute("""
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
            embedding       VECTOR(768),
            metadata        JSONB,
            page_number     INTEGER,
            document_hash   VARCHAR(64),
            chunk_hash      VARCHAR(64)     UNIQUE,
            created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. HNSW index for cosine similarity search (best for RAG)
    op.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # 4. Supporting indexes for filtered retrieval
    op.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_domain_idx
        ON document_chunks(domain)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_standard_idx
        ON document_chunks(standard_number)
        WHERE standard_number IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_document_idx
        ON document_chunks(document_name)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_section_idx
        ON document_chunks(section)
        WHERE section IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS document_chunks_doc_hash_idx
        ON document_chunks(document_hash)
        WHERE document_hash IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS document_chunks CASCADE")
    op.execute("DROP EXTENSION IF EXISTS vector")
