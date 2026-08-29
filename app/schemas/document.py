from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentAnalysisResult(BaseModel):
    filename: str
    file_size: Optional[str] = None
    uploaded_at: str
    summary: str
    extracted_requirements: List[Dict[str, Any]] = []
    compliance_gaps: List[Dict[str, Any]] = []
    referenced_standards: List[Dict[str, Any]] = []


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    file_type: str
    storage_url: Optional[str] = None
    analysis_status: str
    analysis_result: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
