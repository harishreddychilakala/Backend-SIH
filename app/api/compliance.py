"""
Compliance API Endpoints
POST /api/compliance and POST /api/compliance/check
GET  /api/compliance and GET  /api/compliance/history
GET  /api/compliance/{id}
"""
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.compliance import (
    ComplianceCheckRequest, ComplianceResult, ComplianceReportResponse
)
from app.services.compliance_service import ComplianceService

router = APIRouter(prefix="/compliance", tags=["Compliance Checker"])


@router.post("", response_model=ComplianceResult, status_code=status.HTTP_201_CREATED)
@router.post("/check", response_model=ComplianceResult, status_code=status.HTTP_201_CREATED)
def run_compliance_check(
    req: ComplianceCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run an AI-assisted compliance check and store the report."""
    return ComplianceService.run_compliance_check(db=db, user=current_user, req=req)


@router.get("", response_model=List[ComplianceReportResponse])
@router.get("/history", response_model=List[ComplianceReportResponse])
def get_user_compliance_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all past compliance reports for the current user."""
    return ComplianceService.get_user_reports(db=db, user=current_user)
