from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SourceItem(BaseModel):
    title: str
    url: Optional[str] = None
    domain: Optional[str] = None
    source_type: Optional[str] = "official"
    relevance: Optional[str] = None


class ApplicableStandard(BaseModel):
    number: str
    title: str
    status: Optional[str] = "Active"
    category: Optional[str] = None
    qco_applicable: Optional[bool] = False
    verification_status: Optional[str] = "needs_verification"


class RequirementItem(BaseModel):
    text: str
    status: Optional[str] = "check"
    category: Optional[str] = None


class StructuredAIResponse(BaseModel):
    summary: str
    standard: Optional[ApplicableStandard] = None
    requirements: Optional[List[RequirementItem]] = []
    qco: Optional[str] = None
    testing: Optional[str] = None
    certification: Optional[str] = None
    laboratories: Optional[List[str]] = []
    sources: Optional[List[SourceItem]] = []
    verification_status: str = "needs_verification"


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)


class NewChatRequest(BaseModel):
    content: str = Field(..., min_length=1)
    title: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    structured_response: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)
