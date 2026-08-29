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
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _generate_ai_response(prompt: str, history: Optional[list] = None) -> dict:
    """
    Generate AI response using a 2-Tier RAG Architecture:
    1. Tier 1: Local Neon pgvector Knowledge Base (5 core domains, 840 high-precision chunks).
    2. Tier 2: Live BIS Government Portal Search (bis.gov.in / manakonline.in) when local chunks do not contain the answer.
    3. Tier 3: Standard AIService fallback.
    """
    if getattr(settings, "rag_enabled", True):
        try:
            # 1. First search local Neon pgvector document chunks
            top_k = getattr(settings, "rag_top_k", 5)
            chunks = rag_retriever.search(prompt, top_k=top_k)
            
            if chunks and len(chunks) > 0 and chunks[0].get("similarity", 0) >= 0.72:
                logger.info(f"⚡ Tier 1: RAG Retrieved {len(chunks)} relevant local chunks (top sim: {chunks[0].get('similarity', 0):.3f}).")
                structured_ai = rag_generator.generate(
                    question=prompt,
                    retrieved_chunks=chunks,
                    conversation_history=history,
                )
                if structured_ai and structured_ai.get("verification_status") != "no_source_found":
                    return structured_ai
            
            # 2. Tier 2 Fallback: If not in local PDFs, search official BIS Government Web Portal
            logger.info(f"🌐 Tier 2: Searching official BIS Government Portal (bis.gov.in / manakonline.in) for: '{prompt[:60]}...'")
            web_results = bis_web_searcher.search_bis_portal(prompt, max_results=4)
            if web_results:
                structured_ai = rag_generator.generate_from_bis_web(
                    question=prompt,
                    web_results=web_results,
                    conversation_history=history,
                )
                if structured_ai:
                    return structured_ai
        except Exception as e:
            logger.warning(f"⚠️ RAG / BIS Web search error: {e}. Falling back to default AIService.")

    # Fallback to standard Groq/Gemini generation
    return gemini_service.generate_response(prompt, history=history)


class ChatService:
    @staticmethod
    def create_conversation_with_message(
        db: Session,
        user: User,
        prompt: str,
        title: Optional[str] = None,
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

        # Generate AI response (via RAG or AIService)
        structured_ai = _generate_ai_response(prompt)
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

        # Generate AI response via RAG or AIService
        structured_ai = _generate_ai_response(prompt, history=history)
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
