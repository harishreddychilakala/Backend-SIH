"""
BIS SmartAI — RAG Vector Retriever
Performs semantic similarity search in Neon PostgreSQL using pgvector.
Supports domain-aware and standard-number filtering.
All SQL uses parameterized queries — never raw user input in SQL strings.
"""
import re
import logging
from typing import List, Optional, Dict, Any

import psycopg2
import psycopg2.extras

from app.core.config import settings
from rag.embeddings import embedding_service

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_TOP_K = 6
MIN_SIMILARITY = 0.35   # Discard results below this cosine similarity threshold

# Domain keyword mapping for auto-detection
DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "Electrical": [
        "electrical", "electric", "wiring", "cable", "switch", "plug", "socket",
        "voltage", "current", "insulation", "circuit", "meter", "transformer",
        "appliance", "kettle", "iron", "heater", "lamp", "bulb", "fan",
    ],
    "Household Appliances": [
        "household", "appliance", "domestic", "kitchen", "refrigerator", "washing",
        "mixer", "grinder", "cooker", "oven", "microwave", "blender", "juicer",
        "pressure cooker", "water heater", "geyser",
    ],
    "Iron & Steel": [
        "steel", "iron", "tmt", "rebar", "structural", "bar", "rod", "sheet",
        "plate", "coil", "galvanized", "stainless", "alloy", "pig iron", "cast iron",
        "mild steel", "carbon steel", "is 2062", "is 1786",
    ],
    "Food & Agriculture": [
        "food", "agriculture", "pesticide", "fertilizer", "grain", "rice", "wheat",
        "edible oil", "spices", "packaged", "fssai", "agricultural", "crop",
        "dairy", "milk", "food safety",
    ],
    "Textile & Leather": [
        "textile", "fabric", "leather", "garment", "cloth", "yarn", "fiber",
        "cotton", "polyester", "wool", "jute", "synthetic", "dye", "weaving",
        "knitting", "footwear", "shoe", "belt", "bag",
    ],
}

IS_NUMBER_RE = re.compile(r'\bIS\s*(?:No\.?\s*)?(\d+(?:[:\-]\d+(?:[:\-]\d+)?)?)\b', re.IGNORECASE)


def _detect_domain(query: str) -> Optional[str]:
    """
    Try to identify the most likely domain from the query text.
    Returns the domain name or None if uncertain.
    """
    query_lower = query.lower()
    scores: Dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[domain] = score

    if not scores:
        return None
    best = max(scores, key=lambda d: scores[d])
    # Only use the domain filter if there's a reasonably clear signal
    if scores[best] >= 2:
        return best
    return None


def _extract_is_number_from_query(query: str) -> Optional[str]:
    """Extract an IS standard number from a user query if present."""
    m = IS_NUMBER_RE.search(query)
    if m:
        return f"IS {m.group(1)}"
    return None


from app.db.database import engine

def _get_connection():
    """Get a connection from the application's engine pool for fast vector query execution."""
    try:
        return engine.raw_connection()
    except Exception as e:
        logger.warning(f"Engine connection failed: {e}. Falling back to direct connection.")
        return psycopg2.connect(settings.database_url, sslmode="require", connect_timeout=10)


def _release_connection(conn):
    """Return a connection back to the pool."""
    if conn:
        try:
            conn.close()
        except Exception:
            pass


class RAGRetriever:
    """
    Semantic retriever backed by Neon pgvector.
    Generates a query embedding then performs approximate nearest-neighbour search.
    """

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        domain_filter: Optional[str] = None,
        standard_filter: Optional[str] = None,
        min_similarity: float = MIN_SIMILARITY,
        allow_filter_fallback: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search for the most relevant BIS document chunks.

        Args:
            query: The user's question.
            top_k: Number of top results to return.
            domain_filter: Optional domain name to restrict search.
            standard_filter: Optional IS standard number to restrict search.
            min_similarity: Minimum cosine similarity threshold (0-1).
            allow_filter_fallback: If True, falls back to unfiltered search if filtered search returns 0 results.

        Returns:
            List of chunk dicts.
        """
        # 1. Generate query embedding
        query_embedding = embedding_service.embed_query(query)
        if query_embedding is None:
            logger.error("Failed to generate query embedding — returning no results.")
            return []

        # 2. Build parameterized SQL using direct HNSW vector index
        embedding_str = f"[{','.join(str(v) for v in query_embedding)}]"

        params: Dict[str, Any] = {
            "embedding": embedding_str,
            "limit": top_k,
            "min_sim": min_similarity,
        }

        # If explicit domain or standard filter was passed programmatically, apply it
        where_clauses = ["embedding IS NOT NULL"]
        if domain_filter:
            where_clauses.append("LOWER(domain) LIKE LOWER(%(domain_like)s)")
            params["domain_like"] = f"%{domain_filter}%"
        if standard_filter:
            where_clauses.append("LOWER(standard_number) LIKE LOWER(%(std_like)s)")
            params["std_like"] = f"%{standard_filter.replace('IS ', '')}%"

        where_str = " AND ".join(where_clauses)

        sql = f"""
            SELECT
                id,
                domain,
                document_name,
                standard_number,
                standard_title,
                section,
                clause,
                content,
                page_number,
                metadata,
                chunk_index,
                1 - (embedding <=> %(embedding)s::vector) AS similarity
            FROM document_chunks
            WHERE {where_str}
              AND 1 - (embedding <=> %(embedding)s::vector) >= %(min_sim)s
            ORDER BY embedding <=> %(embedding)s::vector
            LIMIT %(limit)s
        """

        # 3. Execute search
        rows = []
        conn = None
        try:
            conn = _get_connection()
            conn.set_session(autocommit=True)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        except Exception as e:
            logger.error(f"RAG retrieval query failed: {e}")
            return []
        finally:
            if conn:
                _release_connection(conn)

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "domain": row["domain"],
                "document_name": row["document_name"],
                "standard_number": row["standard_number"],
                "standard_title": row["standard_title"],
                "section": row["section"],
                "clause": row["clause"],
                "content": row["content"],
                "page_number": row["page_number"],
                "metadata": dict(row["metadata"]) if row["metadata"] else {},
                "chunk_index": row["chunk_index"],
                "similarity": float(row["similarity"]),
            })

        logger.info(
            f"RAG retrieved {len(results)} chunks "
            f"(top similarity: {results[0]['similarity']:.3f} | "
            f"query: '{query[:60]}...')"
        )
        return results

    def check_table_exists(self) -> bool:
        """Verify document_chunks table exists and has data."""
        try:
            conn = _get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
                count = cur.fetchone()[0]
            conn.close()
            logger.info(f"document_chunks table has {count} rows with embeddings.")
            return count > 0
        except Exception as e:
            logger.warning(f"document_chunks table check failed: {e}")
            return False

    def get_domain_stats(self) -> Dict[str, int]:
        """Return chunk counts per domain (for health check / debugging)."""
        try:
            conn = _get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT domain, COUNT(*) as cnt FROM document_chunks GROUP BY domain ORDER BY domain"
                )
                rows = cur.fetchall()
            conn.close()
            return {row[0]: row[1] for row in rows}
        except Exception as e:
            logger.error(f"Failed to get domain stats: {e}")
            return {}


# Singleton
rag_retriever = RAGRetriever()
