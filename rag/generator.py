"""
BIS SmartAI — RAG Generator
Grounded answer generation using retrieved BIS document context.
Uses existing Groq/Gemini AIService with a RAG-specific system prompt.
"""
import json
import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from rag.prompts import RAG_SYSTEM_PROMPT, build_rag_prompt

logger = logging.getLogger(__name__)

# Try importing Groq
try:
    from groq import Groq
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False

# Try importing Gemini
try:
    from google import genai
    from google.genai import types as genai_types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


def _format_sources(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert retrieved chunks into clean source citation objects."""
    sources = []
    seen_ids = set()
    for chunk in chunks:
        chunk_id = chunk.get("id")
        if chunk_id in seen_ids:
            continue
        seen_ids.add(chunk_id)
        sources.append({
            "document": chunk.get("document_name", ""),
            "domain": chunk.get("domain", ""),
            "standard": chunk.get("standard_number"),
            "section": chunk.get("section"),
            "page": chunk.get("page_number"),
            "similarity": round(chunk.get("similarity", 0), 4),
            "chunk_id": chunk_id,
        })
    return sources


def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code fences."""
    text = text.strip()
    # Remove code fences if present
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON: {e}\nRaw text: {text[:200]}")
        return None


class RAGGenerator:
    """
    Generates grounded answers using retrieved BIS document chunks.
    Uses Groq (primary) → Gemini (fallback), same as existing AIService.
    """

    def __init__(self):
        self._groq_client = None
        self._gemini_client = None
        self._init()

    def _init(self):
        # Groq client
        if _GROQ_AVAILABLE and settings.is_groq_configured:
            try:
                self._groq_client = Groq(api_key=settings.groq_api_key)
                logger.info("RAG Generator: Groq client initialized.")
            except Exception as e:
                logger.warning(f"RAG Generator: Groq init failed: {e}")

        # Gemini client (for embeddings we already use it; reuse first key)
        if _GENAI_AVAILABLE and settings.is_gemini_configured:
            try:
                self._gemini_client = genai.Client(api_key=settings.gemini_api_keys[0])
                logger.info("RAG Generator: Gemini client initialized.")
            except Exception as e:
                logger.warning(f"RAG Generator: Gemini init failed: {e}")

    def generate(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        conversation_history: Optional[list] = None,
        target_language: str = "en",
    ) -> Dict[str, Any]:
        """
        Generate a grounded answer from retrieved BIS chunks.

        Args:
            question: The user's question.
            retrieved_chunks: Chunks from RAGRetriever.search().
            conversation_history: Optional prior messages for context.
            target_language: Target output language code ('en', 'hi', 'te').

        Returns:
            Structured response dict compatible with the existing chat service schema.
        """
        sources = _format_sources(retrieved_chunks)
        user_prompt = build_rag_prompt(question, retrieved_chunks, target_language=target_language)

        parsed = None

        # 1. Try Groq (Primary for ultra-fast <1s generation)
        if self._groq_client:
            parsed = self._generate_with_groq(user_prompt, conversation_history)

        # 2. Fallback to Gemini if Groq fails
        if parsed is None and self._gemini_client:
            parsed = self._generate_with_gemini(user_prompt, conversation_history)

        # 3. Absolute fallback if both fail
        if parsed is None:
            logger.error("RAG generation: Both Groq and Gemini failed.")
            parsed = self._fallback_response(question, retrieved_chunks)

        # Inject sources into the response (override what LLM put there)
        parsed["sources"] = sources
        if not parsed.get("rag_context_used"):
            parsed["rag_context_used"] = len(retrieved_chunks) > 0

        # Ensure summary field exists (used by existing chat service)
        if "summary" not in parsed:
            parsed["summary"] = parsed.get("answer", "")

        return parsed

    def generate_from_bis_web(
        self,
        question: str,
        web_results: List[Dict[str, Any]],
        conversation_history: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Generate a grounded answer using live search results from official BIS Government websites.
        Used when the question is not covered by the 5 local indexed PDFs.
        """
        from rag.prompts import build_web_grounded_prompt, WEB_GROUNDED_SYSTEM_PROMPT

        user_prompt = build_web_grounded_prompt(question, web_results)
        parsed = None

        # 1. Try Groq first
        if self._groq_client:
            parsed = self._generate_with_groq(
                user_prompt,
                conversation_history,
                system_prompt=WEB_GROUNDED_SYSTEM_PROMPT,
            )

        # 2. Fallback to Gemini
        if parsed is None and self._gemini_client:
            parsed = self._generate_with_gemini(
                user_prompt,
                conversation_history,
                system_prompt=WEB_GROUNDED_SYSTEM_PROMPT,
            )

        if parsed is None:
            parsed = self._fallback_response(question, [])

        # Inject official web sources
        parsed["sources"] = web_results
        parsed["rag_context_used"] = True
        parsed["source_type"] = "bis_gov_portal"
        if "summary" not in parsed:
            parsed["summary"] = parsed.get("answer", "")

        return parsed

    def _generate_with_groq(
        self,
        user_prompt: str,
        history: Optional[list],
        system_prompt: str = RAG_SYSTEM_PROMPT,
    ) -> Optional[Dict[str, Any]]:
        if not self._groq_client:
            return None
        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for msg in history[-6:]:
                role = "user" if getattr(msg, "role", msg.get("role", "user")) == "user" else "assistant"
                content = getattr(msg, "content", msg.get("content", ""))
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_prompt})

        for model in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"]:
            try:
                completion = self._groq_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.15,
                    max_tokens=3000,
                    response_format={"type": "json_object"},
                )
                content = completion.choices[0].message.content.strip()
                parsed = _parse_llm_json(content)
                if parsed:
                    logger.info(f"RAG generation OK via Groq model: {model}")
                    return parsed
            except Exception as e:
                logger.warning(f"Groq RAG model {model} failed: {e}")
                continue
        return None

    def _generate_with_gemini(
        self,
        user_prompt: str,
        history: Optional[list],
        system_prompt: str = RAG_SYSTEM_PROMPT,
    ) -> Optional[Dict[str, Any]]:
        contents = []
        if history:
            for msg in history[-6:]:
                role_raw = getattr(msg, "role", msg.get("role", "user"))
                role = "user" if role_raw == "user" else "model"
                content = getattr(msg, "content", msg.get("content", ""))
                contents.append(genai_types.Content(role=role, parts=[genai_types.Part(text=content)]))
        contents.append(genai_types.Content(role="user", parts=[genai_types.Part(text=user_prompt)]))

        for model in ["models/gemini-3.5-flash-lite", "models/gemini-3.6-flash", "models/gemini-3.7-flash", "models/gemini-3.5-flash"]:
            try:
                response = self._gemini_client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.15,
                        top_p=0.9,
                        response_mime_type="application/json",
                    ),
                )
                parsed = _parse_llm_json(response.text)
                if parsed:
                    logger.info(f"RAG generation OK via Gemini model: {model}.")
                    return parsed
            except Exception as e:
                logger.warning(f"Gemini RAG model {model} failed: {e}")
                continue
        return None

    def _fallback_response(
        self,
        question: str,
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Last-resort response when both LLM providers fail."""
        if chunks:
            best = chunks[0]
            answer = (
                f"Based on indexed BIS documents, here is relevant information:\n\n"
                f"{best['content'][:600]}\n\n"
                f"(Source: {best['document_name']}, Page {best.get('page_number', '?')})"
            )
        else:
            answer = (
                "The indexed BIS documents do not contain specific information about this query. "
                "Please verify at bis.gov.in for authoritative information."
            )
        return {
            "answer": answer,
            "summary": answer[:200],
            "is_bis_related": True,
            "applicable_standard": None,
            "requirements": [],
            "qco": None,
            "testing": [],
            "certification": [],
            "laboratories": [],
            "sources": [],
            "verification_status": "no_source_found",
            "rag_context_used": len(chunks) > 0,
        }


# Singleton
rag_generator = RAGGenerator()
