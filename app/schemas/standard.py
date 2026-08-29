from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class StandardItem(BaseModel):
    id: str
    number: str
    title: str
    category: str
    subcategory: Optional[str] = None
    status: str
    last_updated: Optional[str] = None
    qco_applicable: bool = False
    bis_mark_required: bool = False
    scope: Optional[str] = None
    overview: Optional[str] = None
    requirements: Optional[List[Dict[str, Any]]] = None
    testing: Optional[Dict[str, Any]] = None
    certification: Optional[Dict[str, Any]] = None
    sources: Optional[List[Dict[str, Any]]] = None


class StandardSearchResponse(BaseModel):
    total: int
    results: List[StandardItem]
    page: int = 1
    limit: int = 20


class SaveStandardRequest(BaseModel):
    standard_id: str
    standard_reference: str
    title: str
    category: Optional[str] = None
    status: Optional[str] = None


class SavedStandardResponse(BaseModel):
    id: str
    user_id: str
    standard_reference: str
    title: str
    category: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
