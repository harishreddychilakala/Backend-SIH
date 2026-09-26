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
        # 1. Check if product matches a curated standard in local database
        matched_curated = None
        search_term = (req.standard_reference or req.product_name or "").lower()
        from app.services.standards_service import CURATED_STANDARDS_DB, StandardsService
        
        for std in CURATED_STANDARDS_DB:
            if req.standard_reference and (req.standard_reference.lower() in std["number"].lower() or std["id"] in req.standard_reference.lower()):
                matched_curated = std
                break
            if any(term in std["title"].lower() or term in std.get("subcategory", "").lower() or term in std.get("scope", "").lower() for term in [req.product_name.lower()]):
                matched_curated = std
                break

        # If not in curated list, attempt discovery
        curated_context = ""
        if matched_curated:
            curated_context = (
                f"\nAUTHENTIC BIS STANDARD FOUND:\n"
                f"- Number: {matched_curated['number']}\n"
                f"- Title: {matched_curated['title']}\n"
                f"- QCO Status: {'Mandatory Statutory QCO' if matched_curated.get('qco_applicable') else 'Voluntary / General'}\n"
                f"- Key Clauses: {json.dumps(matched_curated.get('requirements', []))}\n"
                f"- Key Tests: {json.dumps(matched_curated.get('testing', {}).get('keyTests', []))}\n"
            )

        prompt = f"""Perform an authentic, grounded BIS compliance assessment for this product:
Product Name: {req.product_name}
Category: {req.product_category or 'General'}
Standard Reference (if known): {req.standard_reference or (matched_curated['number'] if matched_curated else 'Not specified')}
Manufacturer / Importer Type: {req.manufacturer_type or 'Domestic Manufacturer'}
Intended Market: {req.intended_market or 'Indian Domestic Market'}
Product Details: {req.description or 'Standard commercial production'}
{curated_context}

Analyze applicable Indian Standards, Quality Control Orders (QCO), testing requirements, and certification schemes.
Generate a structured compliance evaluation JSON object with:
1. "overall_score": integer between 70 and 95
2. "status": one of ["COMPLIANT", "PARTIALLY COMPLIANT", "NEEDS VERIFICATION", "NON-COMPLIANT"]
3. "applicable_standard": {{
     "number": "Official IS number (e.g. IS 374, IS 14756, IS 1009, IS 1786, IS 2082)",
     "title": "Full standard title",
     "qco_mandatory": boolean (true if mandatory QCO in force)
   }}
4. "qco_details": "Clear explanation of QCO applicability, statutory Gazette order, and mandatory deadlines"
5. "breakdown": array of 4 compliance areas. Each area must have:
   - "area": e.g. "Standard Conformance", "Quality Control Order (QCO)", "Laboratory Testing", "Certification & Quality Audit"
   - "score": integer 0-100
   - "status": "passed" / "needs-review" / "missing"
   - "items": list of items with "text" and "status" ("passed" / "needs-review" / "missing")
6. "checklist": array of 5-6 granular checklist items for the manufacturer with:
   - "id": "chk-1", "chk-2", etc.
   - "clause": clause reference (e.g. "Clause 13", "Clause 6", "Clause 8.1")
   - "text": specific measurable technical requirement
   - "category": "Safety" / "Performance" / "Chemical" / "Mechanical"
   - "mandatory": true/false
   - "status": "pending"
7. "confirmed_requirements": list of 3-4 verified requirements derived directly from the standard
8. "unverified_requirements": list of 2-3 requirements requiring accredited laboratory testing or factory inspection
9. "required_documents": list of 4-5 critical documents required for submission (e.g. "Factory Quality Manual", "In-house Test Reports", "Calibration Certificates")
10. "testing_clauses": list of 4-5 specific tests required
11. "certification_steps": list of 4 numbered steps for obtaining the license on Manakonline
12. "next_steps": list of 3-4 actionable next steps for the applicant
13. "verification_status": "verified" or "needs_verification"

Return strictly valid JSON."""

        try:
            ai_res = gemini_service.generate_response(prompt)
            score = ai_res.get("overall_score", 85)
            status_text = ai_res.get("status", "PARTIALLY COMPLIANT")
            std_obj = ai_res.get("applicable_standard") or {}
            
            if matched_curated and not std_obj.get("number"):
                std_obj["number"] = matched_curated["number"]
                std_obj["title"] = matched_curated["title"]
                std_obj["qco_mandatory"] = matched_curated.get("qco_applicable", True)

            std_ref = std_obj.get("number") or (matched_curated["number"] if matched_curated else (req.standard_reference or "IS Standard Required"))
            std_title = std_obj.get("title") or (matched_curated["title"] if matched_curated else "")

            # Build checklist
            raw_checklist = ai_res.get("checklist") or []
            checklist = []
            if raw_checklist and isinstance(raw_checklist, list):
                for idx, item in enumerate(raw_checklist):
                    checklist.append({
                        "id": item.get("id", f"chk-{idx+1}"),
                        "clause": item.get("clause", f"Clause {idx+1}"),
                        "text": item.get("text", "Technical specification requirement"),
                        "category": item.get("category", "Safety"),
                        "mandatory": item.get("mandatory", True),
                        "status": item.get("status", "pending"),
                    })
            elif matched_curated and matched_curated.get("requirements"):
                for idx, r in enumerate(matched_curated.get("requirements", [])):
                    checklist.append({
                        "id": f"chk-{idx+1}",
                        "clause": r.get("clause", f"Clause {idx+1}"),
                        "text": r.get("text", ""),
                        "category": r.get("category", "Safety"),
                        "mandatory": r.get("mandatory", True),
                        "status": "pending",
                    })

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
                    "status": "passed" if std_obj.get("qco_mandatory", True) else "needs-review",
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

            sources = [
                {"title": "Bureau of Indian Standards Official Portal", "url": "https://www.bis.gov.in", "type": "Official"},
                {"title": "BIS Manakonline Portal", "url": "https://www.manakonline.in", "type": "Official"}
            ]
            if matched_curated and matched_curated.get("sources"):
                sources = matched_curated.get("sources")

            disclaimer = (
                "Compliance Assistance Notice: This evaluation is an AI-assisted preparation checklist. "
                "It helps manufacturers and SMEs map technical readiness against Indian Standards. "
                "It does NOT grant official statutory BIS certification or substitute accredited laboratory testing and officer inspection."
            )

            result_data = {
                "product": req.product_name,
                "category": req.product_category or "General",
                "standard": std_ref,
                "standard_title": std_title,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "overall_score": score,
                "status": status_text,
                "qco_details": ai_res.get("qco_details", "Mandatory BIS certification order in effect under statutory gazette."),
                "breakdown": breakdown,
                "checklist": checklist,
                "confirmed_requirements": ai_res.get("confirmed_requirements", [
                    f"Conformity to parameters defined under {std_ref}",
                    "Mandatory marking and labelling as per BIS scheme guidelines",
                    "In-house quality control testing capability"
                ]),
                "unverified_requirements": ai_res.get("unverified_requirements", [
                    "Type testing at BIS-recognized independent testing laboratory",
                    "Factory inspection and auditor verification of quality assurance plan"
                ]),
                "testing_clauses": ai_res.get("testing_clauses", matched_curated.get("testing", {}).get("keyTests", []) if matched_curated else []),
                "required_documents": ai_res.get("required_documents", [
                    "Factory Quality Control Manual & Test Equipment Calibration Records",
                    "Raw Material Test Certificates & Supplier Invoices",
                    "Manufacturing Machinery Layout & Factory Ownership / Lease Deed",
                    "Authorised Signatory Board Resolution / Power of Attorney"
                ]),
                "certification_steps": ai_res.get("certification_steps", [
                    "1. Register on BIS Manakonline (manakonline.in) under Scheme-I or Scheme-II",
                    "2. Submit in-house quality control plan and test equipment calibration reports",
                    "3. Undergo factory audit and sample sealing by BIS certification officers",
                    "4. Complete independent laboratory testing and receive CM/L license number"
                ]),
                "next_steps": ai_res.get("next_steps", [
                    f"Review detailed clauses of {std_ref} to ensure in-house production lines meet tolerances.",
                    "Engage a BIS-recognized laboratory for preliminary prototype testing.",
                    "Submit formal application via BIS Manakonline portal (manakonline.in)."
                ]),
                "legal_disclaimer": disclaimer,
                "sources": sources,
                "verification_status": "verified" if matched_curated else ai_res.get("verification_status", "verified"),
            }
        except Exception as e:
            logger.error(f"Error in Gemini compliance evaluation: {e}")
            score = 80
            status_text = "NEEDS VERIFICATION"
            std_ref = req.standard_reference or "IS Specification"
            result_data = {
                "product": req.product_name,
                "category": req.product_category or "General",
                "standard": std_ref,
                "standard_title": "",
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
                "checklist": [
                    {"id": "chk-1", "clause": "General", "text": "Verify active Indian Standard specification on Manakonline", "category": "General", "mandatory": True, "status": "pending"}
                ],
                "confirmed_requirements": ["Standard specification identification"],
                "unverified_requirements": ["Laboratory testing and physical verification"],
                "next_steps": ["Review standard on official BIS portal", "Submit application on Manakonline"],
                "legal_disclaimer": "This tool provides compliance assistance and does not issue legal certification.",
                "sources": [{"title": "Bureau of Indian Standards", "url": "https://www.bis.gov.in", "type": "Official"}],
                "verification_status": "needs_verification",
            }

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
