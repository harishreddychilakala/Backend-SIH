from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UserUpdate(BaseModel):
    name: Optional[str] = None
    organization: Optional[str] = None
    industry: Optional[str] = None
    role: Optional[str] = None


class UserProfileResponse(BaseModel):
    id: str
    name: str
    email: str
    organization: Optional[str] = None
    industry: Optional[str] = None
    role: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
