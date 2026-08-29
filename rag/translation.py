"""
BIS SmartAI — Multilingual Translation Utility
Handles language detection (heuristic) and query normalization (LLM-based).
Designed to wrap around the existing RAG pipeline without modifying it.
"""
import re
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# ── Supported languages ───────────────────────────────────────────────────────
SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "native": "English", "flag": "🇬🇧"},
    "hi": {"name": "Hindi", "native": "हिन्दी", "flag": "🇮🇳"},
    "te": {"name": "Telugu", "native": "తెలుగు", "flag": "🇮🇳"},
}

# ── Unicode script ranges for heuristic language detection ────────────────────
# Devanagari: U+0900 – U+097F (Hindi, Marathi, Sanskrit, etc.)
_DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')
# Telugu: U+0C00 – U+0C7F
_TELUGU_RE = re.compile(r'[\u0C00-\u0C7F]')


def detect_language(text: str) -> str:
    """
    Detect language from text using Unicode script analysis.
    Returns ISO 639-1 code: 'en', 'hi', or 'te'.

    This is instant (zero-latency, no API call) and 100% accurate for
    distinguishing Hindi/Telugu from English since they use entirely
    different scripts (Devanagari / Telugu script vs Latin).
    """
    if not text or not text.strip():
        return "en"

    # Count characters in each script
    devanagari_count = len(_DEVANAGARI_RE.findall(text))
    telugu_count = len(_TELUGU_RE.findall(text))

    # If significant non-Latin characters found, classify by dominant script
    if devanagari_count >= 2 or telugu_count >= 2:
        if devanagari_count >= telugu_count:
            return "hi"
        return "te"

    return "en"


def get_language_name(lang_code: str) -> str:
    """Get the display name for a language code."""
    return SUPPORTED_LANGUAGES.get(lang_code, {}).get("name", "English")


# ── Query normalization (translate to English for RAG retrieval) ──────────────
# Cache to avoid re-translating repeated queries
@lru_cache(maxsize=256)
def _cached_normalize(query: str, source_lang: str) -> str:
    """Cached wrapper for query normalization."""
    return _do_normalize(query, source_lang)


def _do_normalize(query: str, source_lang: str) -> str:
    """
    Translate a non-English query to English using Groq (fastest LLM).
    Falls back to returning the original query on any error.
    """
    try:
        from groq import Groq
        from app.core.config import settings

        if not settings.is_groq_configured:
            logger.warning("Groq not configured for query normalization, returning original query.")
            return query

        client = Groq(api_key=settings.groq_api_key)
        lang_name = get_language_name(source_lang)

        for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"]:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                f"You are a translator. Translate the following {lang_name} text to English. "
                                "Preserve all technical terms, IS numbers (e.g. IS 1786, IS 302-2-15), "
                                "BIS terminology, and proper nouns exactly as-is. "
                                "Return ONLY the English translation, nothing else."
                            ),
                        },
                        {"role": "user", "content": query},
                    ],
                    temperature=0.1,
                    max_tokens=256,
                )

                translated = response.choices[0].message.content.strip()
                if translated:
                    logger.info(f"🌐 Query normalized: '{query[:40]}' ({source_lang}) → '{translated[:40]}' (en)")
                    return translated
            except Exception as model_err:
                logger.warning(f"Groq translation model {model} failed: {model_err}")

    except Exception as e:
        logger.warning(f"⚠️ Query normalization failed: {e}. Using original query.")

    return query


def normalize_query(query: str, language: str = "en") -> str:
    """
    Normalize a user query to English for RAG vector retrieval.

    If the language is already English, returns the query unchanged.
    If non-English, translates to English using Groq LPU (~200ms).
    Results are cached to avoid repeated translations.

    Args:
        query: The user's original query text.
        language: ISO 639-1 language code ('en', 'hi', 'te').

    Returns:
        English version of the query for embedding/retrieval.
    """
    if language == "en" or not query.strip():
        return query

    return _cached_normalize(query, language)
