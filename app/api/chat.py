"""
Chat API Endpoints
POST /api/chat
POST /api/chat/{conversation_id}/messages
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.chat import (
    NewChatRequest, SendMessageRequest,
    ConversationDetailResponse, MessageResponse
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat & AI Assistant"])


@router.post("", response_model=ConversationDetailResponse, status_code=status.HTTP_201_CREATED)
def create_new_chat(
    req: NewChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start a new conversation with an initial prompt.
    Calls Gemini AI and returns structured response.
    """
    conv, user_msg, ai_msg = ChatService.create_conversation_with_message(
        db=db,
        user=current_user,
        prompt=req.content,
        title=req.title,
        language=req.language or "en",
        image_data=req.image_data,
    )
    return {
        "id": conv.id,
        "user_id": conv.user_id,
        "title": conv.title,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "messages": [user_msg, ai_msg],
    }


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
def send_message(
    conversation_id: str,
    req: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a message within an existing conversation.
    Calls Gemini AI with conversation history and returns AI response.
    """
    user_msg, ai_msg = ChatService.send_message_in_conversation(
        db=db,
        user=current_user,
        conversation_id=conversation_id,
        prompt=req.content,
        language=req.language or "en",
        image_data=req.image_data,
    )
    return ai_msg
