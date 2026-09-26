"""
Standards API Endpoints
GET  /api/standards
GET  /api/standards/{id}
POST /api/standards/compare
POST /api/standards/{id}/explain
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Query, HTTPException, status
from app.schemas.standard import StandardSearchResponse
from app.services.standards_service import StandardsService
from app.services.gemini_service import gemini_service

router = APIRouter(prefix="/standards", tags=["Indian Standards"])


class CompareStandardsRequest(BaseModel):
    standard_a_id: str
    standard_b_id: str


@router.get("", response_model=StandardSearchResponse)
def search_standards(
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Category filter"),
    status: Optional[str] = Query(None, description="Status filter"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Search and filter Indian Standards."""
    return StandardsService.search_standards(
        query=q,
        category=category,
        status_filter=status,
        page=page,
        limit=limit,
    )


@router.get("/{standard_id}")
def get_standard(standard_id: str):
    """Get full details for a specific Indian Standard."""
    return StandardsService.get_standard_by_id(standard_id)


@router.post("/compare")
def compare_standards(req: CompareStandardsRequest):
    """
    Compare two Indian Standards side-by-side with structured technical analysis,
    clause-by-clause verification, and source traceability.
    """
    return StandardsService.compare_standards_structured(req.standard_a_id, req.standard_b_id)


@router.post("/{standard_id}/explain")
def explain_standard(standard_id: str):
    """
    Generate conversational AI deep-dive explanation of an Indian Standard.
    """
    std = StandardsService.get_standard_by_id(standard_id)
    prompt = f"Explain the Indian Standard {std.get('number')} - {std.get('title')} in simple, practical language for a manufacturer or consumer. Explain its scope, why it matters, main safety/quality clauses, and certification process."
    return gemini_service.generate_response(prompt)
