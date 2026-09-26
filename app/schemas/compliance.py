from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ComplianceCheckRequest(BaseModel):
    product_name: str = Field(..., min_length=2)
    product_category: Optional[str] = None
    description: Optional[str] = None
    standard_reference: Optional[str] = None
    manufacturer_type: Optional[str] = None
    intended_market: Optional[str] = None


class ComplianceAreaItem(BaseModel):
    text: str
    status: str


class ComplianceArea(BaseModel):
    area: str
    score: int
    status: str
    items: List[ComplianceAreaItem]


class ComplianceChecklistItem(BaseModel):
    id: str
    clause: Optional[str] = None
    text: str
    category: str = "Technical"
    mandatory: bool = True
    status: str = "pending"  # met / pending / needs_test


class ComplianceSource(BaseModel):
    title: str
    url: Optional[str] = None
    type: Optional[str] = "Official"


class ComplianceResult(BaseModel):
    product: str
    category: Optional[str] = None
    standard: Optional[str] = None
    standard_title: Optional[str] = None
    checked_at: str
    overall_score: int
    status: str
    qco_details: Optional[str] = None
    breakdown: List[ComplianceArea]
    checklist: Optional[List[ComplianceChecklistItem]] = None
    confirmed_requirements: Optional[List[str]] = None
    unverified_requirements: Optional[List[str]] = None
    testing_clauses: Optional[List[str]] = None
    required_documents: Optional[List[str]] = None
    certification_steps: Optional[List[str]] = None
    next_steps: List[str]
    legal_disclaimer: Optional[str] = None
    sources: Optional[List[ComplianceSource]] = None
    verification_status: str = "needs_verification"


class ComplianceReportResponse(BaseModel):
    id: str
    user_id: str
    product_name: str
    product_category: Optional[str] = None
    standard_reference: Optional[str] = None
    overall_score: int
    status: str
    result_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
