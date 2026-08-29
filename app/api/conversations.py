"""
Conversations API Endpoints
GET    /api/conversations
GET    /api/conversations/{id}
DELETE /api/conversations/{id}
GET    /api/conversations/{id}/messages
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.chat import ConversationResponse, ConversationDetailResponse, MessageResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationResponse])
def get_conversations(
    search: Optional[str] = Query(None, description="Search conversation titles"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all conversations for the authenticated user (optimized — no N+1 queries)."""
    convs = ChatService.get_user_conversations(
        db=db,
        user=current_user,
        search=search,
        page=page,
        limit=limit,
    )
    # Service now returns dicts directly with last_message included
    results = []
    for c in convs:
        results.append(
            ConversationResponse(
                id=c["id"],
                user_id=c["user_id"],
                title=c["title"],
                created_at=c["created_at"],
                updated_at=c["updated_at"],
                last_message=c.get("last_message"),
            )
        )
    return results


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation_detail(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific conversation and all its messages."""
    conv = ChatService.get_conversation(db=db, user=current_user, conversation_id=conversation_id)
    return conv


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all messages for a specific conversation."""
    conv = ChatService.get_conversation(db=db, user=current_user, conversation_id=conversation_id)
    return conv.messages


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation belonging to the authenticated user."""
    ChatService.delete_conversation(db=db, user=current_user, conversation_id=conversation_id)
    return None
