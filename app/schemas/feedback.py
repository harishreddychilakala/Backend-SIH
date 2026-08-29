from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: str
    user_id: str
    rating: int
    comment: Optional[str] = None
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
