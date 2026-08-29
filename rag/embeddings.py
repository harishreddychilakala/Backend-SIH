"""
BIS SmartAI — Embedding Module
Uses Google gemini-embedding-001 with Matryoshka truncation to 768 dims.
768 dimensions: compatible with pgvector HNSW index (max 2000 dims).
Embedding model is isolated here so it can be swapped without touching RAG logic.
"""
import logging
import time
from typing import List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "models/gemini-embedding-001"   # Google Generative AI
EMBEDDING_DIMENSION = 768                          # Matryoshka truncation to 768 (HNSW-compatible)
MAX_RETRIES = 3
RETRY_DELAY = 2.0                                  # seconds between retries
BATCH_SIZE = 20                                    # Max texts per batch embedding call

# ── Import SDK ────────────────────────────────────────────────────────────────
try:
    from google import genai
    from google.genai import types as genai_types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    logger.error("google-genai SDK not installed. Run: pip install google-genai")


class EmbeddingService:
    """
    Isolated embedding service backed by Google gemini-embedding-001.
    Uses Matryoshka truncation to 768 dimensions for pgvector HNSW compatibility.
    Exposes embed_text(), embed_query(), embed_documents().
    """

    def __init__(self):
        self._client: Optional[object] = None
        self._model = EMBEDDING_MODEL
        self.dimension = EMBEDDING_DIMENSION
        self._initialized = False
        self._init()

    def _init(self):
        """Initialize embedding client from configured API key."""
        if not _GENAI_AVAILABLE:
            logger.error("Cannot initialize embeddings: google-genai not installed.")
            return

        api_key = None
        if settings.gemini_api_keys:
            api_key = settings.gemini_api_keys[0]
        elif settings.gemini_api_key:
            api_key = settings.gemini_api_key

        if not api_key:
            logger.warning(
                "GEMINI_API_KEY not configured. Embeddings will not work. "
                "Add GEMINI_API_KEY to backend/.env"
            )
            return

        try:
            self._client = genai.Client(api_key=api_key)
            self._initialized = True
            logger.info(
                f"Embedding service initialized: {self._model} "
                f"({self.dimension} dims via Matryoshka truncation)"
            )
        except Exception as e:
            logger.error(f"Failed to initialize embedding client: {e}")

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._client is not None

    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Embed a single text string.
        Returns list of 768 floats or None on failure.
        """
        if not self.is_ready:
            logger.error("Embedding service not initialized.")
            return None
        if not text or not text.strip():
            logger.warning("embed_text called with empty text.")
            return None

        for attempt in range(MAX_RETRIES):
            try:
                result = self._client.models.embed_content(
                    model=self._model,
                    contents=text.strip(),
                    config=genai_types.EmbedContentConfig(
                        output_dimensionality=self.dimension,   # Matryoshka truncation
                    ),
                )
                if result.embeddings and result.embeddings[0].values:
                    vec = list(result.embeddings[0].values)
                    return vec
                logger.warning(f"Empty embedding response on attempt {attempt + 1}")
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"Embedding attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {RETRY_DELAY}s..."
                    )
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Embedding failed after {MAX_RETRIES} attempts: {e}")
        return None

    def embed_query(self, query: str) -> Optional[List[float]]:
        """
        Embed a user query for retrieval.
        Same as embed_text for gemini-embedding-001.
        """
        return self.embed_text(query)

    def embed_documents(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Embed a list of document texts.
        Returns a list of embeddings (same length as input), with None for failures.
        Batches requests to respect rate limits.
        """
        if not self.is_ready:
            logger.error("Embedding service not initialized.")
            return [None] * len(texts)

        results: List[Optional[List[float]]] = []
        total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            for text in batch:
                vec = self.embed_text(text)
                results.append(vec)
                time.sleep(0.08)   # Respect rate limits

            logger.info(
                f"Embedded batch {batch_num}/{total_batches} "
                f"({len(results)}/{len(texts)} total)"
            )

        return results


# Singleton — import this throughout the RAG pipeline
embedding_service = EmbeddingService()
EMBEDDING_DIMENSION = embedding_service.dimension
