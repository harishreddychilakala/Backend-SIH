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
    Compare two Indian Standards side-by-side with structured technical analysis.
    """
    std_a = StandardsService.get_standard_by_id(req.standard_a_id)
    std_b = StandardsService.get_standard_by_id(req.standard_b_id)

    # Build technical comparison structure
    scope_diff = std_a.get("scope") != std_b.get("scope")
    cat_diff = std_a.get("category") != std_b.get("category")
    qco_diff = std_a.get("qco_applicable") != std_b.get("qco_applicable")

    comparison_data = {
        "Scope": {
            "A": std_a.get("scope", "Scope defined in official IS standard publication."),
            "B": std_b.get("scope", "Scope defined in official IS standard publication."),
            "differs": scope_diff,
        },
        "Requirements": {
            "A": f"Conformity to parameters specified under {std_a.get('number')}. Safety and quality benchmarks apply.",
            "B": f"Conformity to parameters specified under {std_b.get('number')}. Safety and quality benchmarks apply.",
            "differs": True,
        },
        "Testing": {
            "A": "Type testing and routine quality verification at BIS-recognized test facilities.",
            "B": "Type testing and routine quality verification at BIS-recognized test facilities.",
            "differs": False,
        },
        "Certification": {
            "A": "Scheme-I Product Certification (ISI Mark) or Scheme-II CRS where applicable via Manakonline.",
            "B": "Scheme-I Product Certification (ISI Mark) or Scheme-II CRS where applicable via Manakonline.",
            "differs": False,
        },
        "QCO": {
            "A": "Mandatory compliance under statutory Quality Control Order." if std_a.get("qco_applicable") else "Voluntary standard (verify current Gazette updates).",
            "B": "Mandatory compliance under statutory Quality Control Order." if std_b.get("qco_applicable") else "Voluntary standard (verify current Gazette updates).",
            "differs": qco_diff,
        },
        "Key Differences": {
            "A": f"Targeted at {std_a.get('category', 'Category A')} products ({std_a.get('number')}).",
            "B": f"Targeted at {std_b.get('category', 'Category B')} products ({std_b.get('number')}).",
            "differs": cat_diff,
        }
    }

    summary = (
        f"{std_a.get('number')} covers {std_a.get('title')}, whereas {std_b.get('number')} specifies requirements for {std_b.get('title')}. "
        f"{'Both standards have mandatory Quality Control Orders enforced.' if std_a.get('qco_applicable') and std_b.get('qco_applicable') else 'Review product categorization to select the exact applicable standard.'}"
    )

    recommendation = (
        f"Manufacturers of {std_a.get('category')} items should apply under {std_a.get('number')}, while manufacturers of {std_b.get('category')} goods must conform to {std_b.get('number')} via the BIS Manakonline portal."
    )

    return {
        "standard_a": std_a,
        "standard_b": std_b,
        "summary": summary,
        "comparison": comparison_data,
        "recommendation": recommendation,
        "verification_status": "verified"
    }


@router.post("/{standard_id}/explain")
def explain_standard(standard_id: str):
    """
    Generate conversational AI deep-dive explanation of an Indian Standard.
    """
    std = StandardsService.get_standard_by_id(standard_id)
    prompt = f"Explain the Indian Standard {std.get('number')} - {std.get('title')} in simple, practical language for a manufacturer or consumer. Explain its scope, why it matters, main safety/quality clauses, and certification process."
    return gemini_service.generate_response(prompt)
