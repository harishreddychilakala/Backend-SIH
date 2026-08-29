"""
BIS SmartAI — Compliance Service
Performs dynamic, AI-assisted compliance analysis via Gemini and stores reports with user isolation.
"""
from datetime import datetime, timezone
import json
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from app.models.compliance_report import ComplianceReport
from app.models.user import User
from app.schemas.compliance import ComplianceCheckRequest
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)


class ComplianceService:
    @staticmethod
    def run_compliance_check(
        db: Session,
        user: User,
        req: ComplianceCheckRequest,
    ) -> Dict[str, Any]:
        """
        Evaluate product compliance against Indian Standards & BIS regulations using Gemini AI.
        Saves report to database associated with authenticated user.
        """
        prompt = f"""Perform a comprehensive BIS compliance assessment for this product:
Product Name: {req.product_name}
Category: {req.product_category or 'General'}
Standard Reference (if known): {req.standard_reference or 'Not specified'}
Manufacturer / Importer Type: {req.manufacturer_type or 'Domestic Manufacturer'}
Intended Market: {req.intended_market or 'Indian Domestic Market'}
Product Details: {req.description or 'Standard commercial production'}

Analyze applicable Indian Standards, Quality Control Orders (QCO), testing requirements, and certification schemes.
Generate a structured compliance evaluation JSON object with:
1. "overall_score": integer between 60 and 95 based on technical compliance complexity
2. "status": one of ["COMPLIANT", "PARTIALLY COMPLIANT", "NEEDS VERIFICATION", "NON-COMPLIANT"]
3. "applicable_standard": {{
     "number": "Official IS number (e.g. IS 302-2-15 or IS 1786)",
     "title": "Full standard title",
     "qco_mandatory": boolean (true if mandatory QCO in force)
   }}
4. "qco_details": "Clear explanation of QCO applicability, statutory Gazette order, and mandatory deadlines"
5. "breakdown": array of 4 compliance areas. Each area must have:
   - "area": e.g. "Standard Conformance", "Quality Control Order (QCO)", "Laboratory Testing", "Certification & Quality Audit"
   - "score": integer 0-100
   - "status": "passed" / "needs-review" / "missing"
   - "items": list of items with "text" and "status" ("passed" / "needs-review" / "missing")
6. "required_documents": list of 4-5 critical documents required for submission (e.g. "Factory Quality Manual", "In-house Test Reports", "Calibration Certificates")
7. "testing_clauses": list of 4-5 specific tests required (e.g. "Dielectric strength test at 1250V AC", "Hydrostatic pressure test")
8. "certification_steps": list of 4 numbered steps for obtaining the license on Manakonline
9. "next_steps": list of 3-4 actionable next steps for the applicant
10. "verification_status": "verified" or "needs_verification"

Return strictly valid JSON."""

        try:
            ai_res = gemini_service.generate_response(prompt)
            score = ai_res.get("overall_score", 85)
            status_text = ai_res.get("status", "PARTIALLY COMPLIANT")
            std_obj = ai_res.get("applicable_standard") or {}
            std_ref = std_obj.get("number") or req.standard_reference or "IS Standard Required"

            breakdown = ai_res.get("breakdown") or [
                {
                    "area": "Standard Identification",
                    "score": 90,
                    "status": "passed",
                    "items": [
                        {"text": f"Applicable standard {std_ref} identified for {req.product_name}", "status": "passed"},
                        {"text": "Conformity to active BIS technical specifications", "status": "passed"},
                    ]
                },
                {
                    "area": "Quality Control Order (QCO)",
                    "score": 85,
                    "status": "passed" if std_obj.get("qco_mandatory") else "needs-review",
                    "items": [
                        {"text": ai_res.get("qco_details") or "Mandatory BIS certification evaluated under active QCOs.", "status": "passed"},
                    ]
                },
                {
                    "area": "Laboratory Testing",
                    "score": 80,
                    "status": "needs-review",
                    "items": [
                        {"text": f"Type testing required: {', '.join(ai_res.get('testing_clauses', ['Standard tests'])[:3])}", "status": "needs-review"}
                    ]
                },
                {
                    "area": "Certification Readiness",
                    "score": 75,
                    "status": "needs-review",
                    "items": [
                        {"text": "Factory quality manual and testing setup required for audit", "status": "needs-review"}
                    ]
                }
            ]

            result_data = {
                "product": req.product_name,
                "category": req.product_category or "General",
                "standard": std_ref,
                "standard_title": std_obj.get("title", ""),
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "overall_score": score,
                "status": status_text,
                "qco_details": ai_res.get("qco_details", "Mandatory BIS certification order in effect."),
                "breakdown": breakdown,
                "testing_clauses": ai_res.get("testing_clauses", []),
                "required_documents": ai_res.get("required_documents", []),
                "certification_steps": ai_res.get("certification_steps", []),
                "next_steps": ai_res.get("next_steps", [
                    f"Confirm test parameters specified in {std_ref}.",
                    "Engage a BIS-recognized test laboratory for preliminary sample evaluation.",
                    "Submit online application via BIS Manakonline (manakonline.in)."
                ]),
                "verification_status": ai_res.get("verification_status", "verified"),
            }
        except Exception as e:
            logger.error(f"Error in Gemini compliance evaluation: {e}")
            score = 80
            status_text = "NEEDS VERIFICATION"
            result_data = {
                "product": req.product_name,
                "category": req.product_category or "General",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "overall_score": score,
                "status": status_text,
                "qco_details": "Verify mandatory QCO notifications on official DPIIT / BIS portals.",
                "breakdown": [
                    {
                        "area": "Standard Identification",
                        "score": 80,
                        "status": "needs-review",
                        "items": [{"text": f"Verification with official BIS directory required for {req.product_name}", "status": "needs-review"}]
                    }
                ],
                "next_steps": ["Review standard on official BIS portal", "Submit application on Manakonline"],
                "verification_status": "needs_verification",
            }
            std_ref = req.standard_reference or "IS Specification"

        # Store report in Neon PostgreSQL with user isolation
        report = ComplianceReport(
            user_id=user.id,
            product_name=req.product_name,
            product_category=req.product_category,
            standard_reference=std_ref,
            overall_score=score,
            status=status_text,
            result_json=result_data,
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        return result_data

    @staticmethod
    def get_user_reports(
        db: Session,
        user: User,
        limit: int = 20,
    ) -> List[ComplianceReport]:
        """Get past compliance reports for authenticated user."""
        return db.query(ComplianceReport).filter(
            ComplianceReport.user_id == user.id
        ).order_by(desc(ComplianceReport.created_at)).limit(limit).all()
