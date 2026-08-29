"""
BIS SmartAI — Chat Service
Manages user conversations and messages with user-level isolation.
"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from fastapi import HTTPException, status
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
import logging
from app.core.config import settings
from app.services.gemini_service import gemini_service
from rag.retriever import rag_retriever
from rag.generator import rag_generator
from rag.bis_web_searcher import bis_web_searcher
from rag.translation import detect_language, normalize_query
import base64
from datetime import datetime, timezone
from app.services.vision_service import vision_service

logger = logging.getLogger(__name__)


def _extract_image_bytes(image_data: str) -> tuple[Optional[bytes], str]:
    """Parse base64 data URL into raw bytes and mime type."""
    if not image_data or not isinstance(image_data, str):
        return None, "image/jpeg"
    try:
        if "," in image_data:
            header, b64 = image_data.split(",", 1)
            mime = header.split(";")[0].replace("data:", "") or "image/jpeg"
            return base64.b64decode(b64), mime
        return base64.b64decode(image_data), "image/jpeg"
    except Exception as e:
        logger.warning(f"Failed to decode image_data: {e}")
        return None, "image/jpeg"


def _generate_ai_response(
    prompt: str,
    history: Optional[list] = None,
    language: str = "en",
    image_data: Optional[str] = None,
) -> dict:
    """
    Generate AI response using ultra-fast Multilingual RAG + Multimodal Vision Architecture:
    1. If image attachment provided, run Vision AI product identification
    2. Detect language if auto/unspecified
    3. Normalize non-English query to English for semantic retrieval
    4. Retrieve top chunks from Neon pgvector
    5. Generate grounded answer in user's target language
    6. Direct High-Performance AIService fallback.
    """
    # 1. Process image attachment if present
    vision_context = ""
    vision_details = None
    if image_data:
        img_bytes, mime_type = _extract_image_bytes(image_data)
        if img_bytes:
            try:
                vision_details = vision_service.analyze_image_bytes(img_bytes, mime_type=mime_type)
                prod_name = vision_details.get("product_name", "Identified Product")
                std_num = vision_details.get("applicable_standard", {}).get("number", "Unknown Standard")
                markings = ", ".join(vision_details.get("detected_markings", []))
                vision_context = f"[PHOTO ANALYSIS: Identified Product: '{prod_name}', Applicable Standard: '{std_num}', Visible Markings: '{markings}']\n"
            except Exception as ve:
                logger.warning(f"Vision analysis in chat failed: {ve}")

    augmented_prompt = f"{vision_context}{prompt}" if vision_context else prompt

    # Auto-detect language if not explicitly provided or if default 'en' but text is Indian script
    effective_lang = language
    if not effective_lang or effective_lang == "en":
        detected = detect_language(prompt)
        if detected != "en":
            effective_lang = detected

    # Normalize query for vector search (translates to English if needed; instant if already English)
    search_prompt = normalize_query(augmented_prompt, language=effective_lang) if effective_lang != "en" else augmented_prompt

    if getattr(settings, "rag_enabled", True):
        try:
            # Search local Neon pgvector document chunks using normalized query
            top_k = getattr(settings, "rag_top_k", 4)
            chunks = rag_retriever.search(search_prompt, top_k=top_k)
            
            if chunks and len(chunks) > 0 and chunks[0].get("similarity", 0) >= 0.35:
                logger.info(f"⚡ Tier 1: Local PDF RAG matched {len(chunks)} chunks (top similarity: {chunks[0].get('similarity', 0):.3f}) for: '{search_prompt[:50]}'")
                structured_ai = rag_generator.generate(
                    question=augmented_prompt,
                    retrieved_chunks=chunks,
                    conversation_history=history,
                    target_language=effective_lang,
                )
                if structured_ai and structured_ai.get("verification_status") != "no_source_found":
                    structured_ai["language"] = effective_lang
                    if vision_details:
                        structured_ai["vision_identified_product"] = vision_details.get("product_name")
                    return structured_ai
        except Exception as e:
            logger.warning(f"⚠️ RAG retrieval error: {e}. Falling back to default AIService.")

    # Fast direct generation via Groq / Gemini
    prompt_to_send = augmented_prompt
    if effective_lang == "hi":
        prompt_to_send = f"{augmented_prompt}\n\n(Please reply entirely in fluent Hindi / हिन्दी while preserving official IS standard numbers and technical terms in English)."
    elif effective_lang == "te":
        prompt_to_send = f"{augmented_prompt}\n\n(Please reply entirely in fluent Telugu / తెలుగు while preserving official IS standard numbers and technical terms in English)."

    resp = gemini_service.generate_response(prompt_to_send, history=history)
    resp["language"] = effective_lang
    if vision_details:
        resp["vision_identified_product"] = vision_details.get("product_name")
    return resp


class ChatService:
    @staticmethod
    def create_conversation_with_message(
        db: Session,
        user: User,
        prompt: str,
        title: Optional[str] = None,
        language: str = "en",
        image_data: Optional[str] = None,
    ) -> Tuple[Conversation, Message, Message]:
        """
        Create a new conversation, record user message, call RAG / Gemini AI, record AI response.
        Enforces user isolation.
        """
        # Generate clean title if not given
        if not title:
            clean_title = prompt.strip().replace("\n", " ")
            if len(clean_title) > 60:
                clean_title = clean_title[:57] + "..."
            title = clean_title

        conv = Conversation(
            user_id=user.id,
            title=title,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

        # Store user message
        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=prompt,
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # Generate AI response (via Multilingual RAG + Vision AI)
        structured_ai = _generate_ai_response(prompt, language=language, image_data=image_data)
        ai_summary = structured_ai.get("summary") or structured_ai.get("answer", "Analysis completed.")

        # Store AI message
        ai_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=ai_summary,
            structured_response=structured_ai,
        )
        db.add(ai_msg)

        # Explicitly update conversation updated_at on every new message
        conv.updated_at = datetime.now(timezone.utc)
        db.add(conv)

        db.commit()
        db.refresh(ai_msg)
        db.refresh(conv)

        return conv, user_msg, ai_msg

    @staticmethod
    def send_message_in_conversation(
        db: Session,
        user: User,
        conversation_id: str,
        prompt: str,
        language: str = "en",
        image_data: Optional[str] = None,
    ) -> Tuple[Message, Message]:
        """
        Add a message to an existing conversation, call RAG / Gemini AI, record response.
        Enforces user isolation.
        """
        # Verify conversation belongs to this user
        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        ).first()

        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied.",
            )

        # Fetch history for context (last 10 messages for efficiency)
        history = db.query(Message).filter(
            Message.conversation_id == conv.id
        ).order_by(Message.created_at).limit(20).all()

        # Store user message FIRST
        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=prompt,
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # Generate AI response via Multilingual RAG or AIService
        structured_ai = _generate_ai_response(prompt, history=history, language=language, image_data=image_data)
        ai_summary = structured_ai.get("summary") or structured_ai.get("answer", "Analysis completed.")

        ai_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=ai_summary,
            structured_response=structured_ai,
        )
        db.add(ai_msg)

        # Always bump updated_at on conversation
        conv.updated_at = datetime.now(timezone.utc)
        db.add(conv)

        db.commit()
        db.refresh(ai_msg)

        return user_msg, ai_msg

    @staticmethod
    def get_user_conversations(
        db: Session,
        user: User,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> List[dict]:
        """
        Get conversations for the authenticated user with optimized last-message preview.
        Uses a single efficient query — no N+1 loading.
        Returns list of dicts with id, title, updated_at, created_at, last_message.
        """
        offset = (page - 1) * limit

        # Build base query with subquery for last message (avoids N+1)
        sql = text("""
            SELECT
                c.id,
                c.user_id,
                c.title,
                c.created_at,
                c.updated_at,
                (
                    SELECT m.content
                    FROM messages m
                    WHERE m.conversation_id = c.id
                    ORDER BY m.created_at DESC
                    LIMIT 1
                ) AS last_message
            FROM conversations c
            WHERE c.user_id = :user_id
            {search_clause}
            ORDER BY c.updated_at DESC
            LIMIT :limit OFFSET :offset
        """.format(
            search_clause="AND c.title LIKE :search" if search else ""
        ))

        params = {"user_id": user.id, "limit": limit, "offset": offset}
        if search:
            params["search"] = f"%{search.strip()}%"

        rows = db.execute(sql, params).fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row.id,
                "user_id": row.user_id,
                "title": row.title,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "last_message": row.last_message,
            })
        return results

    @staticmethod
    def get_conversation(db: Session, user: User, conversation_id: str) -> Conversation:
        """Get single conversation with user isolation."""
        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        ).first()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied.",
            )
        return conv

    @staticmethod
    def delete_conversation(db: Session, user: User, conversation_id: str) -> bool:
        """Delete conversation with user isolation."""
        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        ).first()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied.",
            )
        db.delete(conv)
        db.commit()
        return True
