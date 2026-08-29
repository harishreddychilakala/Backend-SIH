"""
BIS SmartAI — Standards & Saved Standards Service
Provides Indian Standards exploration, filtering, AI dynamic search, and user-isolated bookmarking.
"""
import json
import logging
import re
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from app.models.saved_standard import SavedStandard
from app.models.user import User
from app.schemas.standard import SaveStandardRequest
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

# Master curated reference database of Indian Standards (IS)
CURATED_STANDARDS_DB = [
    {
        "id": "is-302-2-15",
        "number": "IS 302-2-15",
        "title": "Safety of Household and Similar Electrical Appliances — Particular Requirements for Appliances for Heating Liquids",
        "category": "Electrical Appliances",
        "subcategory": "Heating Appliances",
        "status": "Active",
        "last_updated": "2023-08-15",
        "qco_applicable": True,
        "bis_mark_required": True,
        "scope": "Covers safety requirements for electric kettles, coffee makers, water heaters, and similar appliances for heating liquids for household and similar use, rated voltage up to 250V.",
        "overview": "Specifies electrical safety, protection against electric shock, resistance to moisture, abnormal operation, thermal cut-outs, and mechanical hazards.",
        "requirements": [
            {"id": "req-01", "text": "Automatic thermal cut-out protection required", "category": "Safety", "mandatory": True},
            {"id": "req-02", "text": "Insulation resistance >= 2 MΩ at 500V DC", "category": "Electrical", "mandatory": True},
            {"id": "req-03", "text": "Dielectric strength test at 1250V AC for 1 minute", "category": "Electrical", "mandatory": True},
            {"id": "req-04", "text": "Leakage current under normal operation < 0.75 mA", "category": "Electrical", "mandatory": True},
            {"id": "req-05", "text": "Boil-dry protection and tip-over stability test", "category": "Mechanical", "mandatory": True},
        ],
        "testing": {
            "duration": "4–6 weeks",
            "labs": 18,
            "keyTests": ["Dielectric strength test", "Insulation resistance", "Leakage current test", "Temperature rise test", "Stability test", "Endurance test"],
        },
        "certification": {
            "scheme": "Scheme I — Product Certification (ISI Mark)",
            "process": ["Submit application on Manakonline", "Factory audit & inspection by BIS auditor", "Sample testing at BIS-recognized laboratory", "Grant of license to use Standard Mark"],
        },
        "sources": [
            {"title": "Bureau of Indian Standards Official Portal", "url": "https://www.bis.gov.in", "type": "Official"},
            {"title": "BIS Manakonline e-Portal", "url": "https://www.manakonline.in", "type": "Official"}
        ]
    },
    {
        "id": "is-1293-2019",
        "number": "IS 1293:2019",
        "title": "Plugs and Socket-Outlets for Domestic and Similar Purposes",
        "category": "Electrical Wiring & Accessories",
        "subcategory": "Plugs & Sockets",
        "status": "Active",
        "last_updated": "2023-04-10",
        "qco_applicable": True,
        "bis_mark_required": True,
        "scope": "Covers plugs and fixed or portable socket-outlets for A.C. only, with a rated voltage not exceeding 250V and a rated current not exceeding 16A.",
        "overview": "Ensures mechanical strength, insulation, protection against accidental contact with live parts, shutter protection, and resistance to abnormal heating.",
        "requirements": [
            {"id": "req-01", "text": "Solid shutter protection on phase and neutral sockets", "category": "Safety", "mandatory": True},
            {"id": "req-02", "text": "Temperature rise limit not exceeding 45°C during continuous load", "category": "Thermal", "mandatory": True},
            {"id": "req-03", "text": "Mechanical impact resistance and drop test", "category": "Mechanical", "mandatory": True},
            {"id": "req-04", "text": "Resistance to heat, fire and tracking as per Glow Wire Test", "category": "Flammability", "mandatory": True}
        ],
        "testing": {
            "duration": "3–5 weeks",
            "labs": 24,
            "keyTests": ["Temperature rise test", "Insulation resistance", "Mechanical endurance test (10,000 cycles)", "Glow wire test", "Drop and impact test"]
        },
        "certification": {
            "scheme": "Scheme I — Product Certification (ISI Mark)",
            "process": ["Online application via Manakonline", "Factory audit & quality verification", "Third-party laboratory testing", "Grant of CM/L licence"]
        },
        "sources": [
            {"title": "DPIIT Electrical Accessories QCO", "url": "https://dpiit.gov.in", "type": "Official Gazette"}
        ]
    },
    {
        "id": "is-13252-part-1",
        "number": "IS 13252 (Part 1)",
        "title": "Information Technology Equipment — Safety (General Requirements)",
        "category": "Electronics & IT",
        "subcategory": "IT Equipment",
        "status": "Active",
        "last_updated": "2022-11-20",
        "qco_applicable": True,
        "bis_mark_required": True,
        "scope": "Applies to mains-powered or battery-powered information technology equipment, including computer equipment, power adapters, displays, and telecommunication devices.",
        "overview": "Specifies safety against electric shock, energy hazards, fire, mechanical and heat hazards, radiation and chemical hazards.",
        "requirements": [
            {"id": "req-01", "text": "Electric strength test and creepage/clearance distance adherence", "category": "Electrical", "mandatory": True},
            {"id": "req-02", "text": "Thermal protection against overheating and component fire propagation", "category": "Safety", "mandatory": True},
            {"id": "req-03", "text": "Acoustic noise limits and touch temperature safety", "category": "Ergonomics", "mandatory": True}
        ],
        "testing": {
            "duration": "2–4 weeks",
            "labs": 35,
            "keyTests": ["Dielectric breakdown test", "Fault condition testing", "Flammability classification", "Leakage current test"]
        },
        "certification": {
            "scheme": "Scheme II — Compulsory Registration Scheme (CRS)",
            "process": ["Sample testing in BIS-recognized lab in India", "Upload test report on CRS portal", "Receive R-Number (Registration Number)", "Affix Standard CRS Mark"]
        },
        "sources": [
            {"title": "MeitY Electronics & IT Goods Order", "url": "https://www.meity.gov.in", "type": "Official Gazette"}
        ]
    },
    {
        "id": "is-1786",
        "number": "IS 1786",
        "title": "High Strength Deformed Steel Bars and Wires for Concrete Reinforcement (TMT Steel Bars)",
        "category": "Steel & Metals",
        "subcategory": "Reinforcement Steel",
        "status": "Active",
        "last_updated": "2023-09-01",
        "qco_applicable": True,
        "bis_mark_required": True,
        "scope": "Covers the requirements of deformed steel bars and wires for use as reinforcement in concrete in grades Fe 415, Fe 415D, Fe 500, Fe 500D, Fe 550, Fe 550D, Fe 600.",
        "overview": "Defines chemical composition limits (Carbon, Sulphur, Phosphorus), tensile properties (Yield stress, Ultimate tensile strength, Elongation), and bend/rebend characteristics.",
        "requirements": [
            {"id": "req-01", "text": "Chemical composition limits: Carbon <= 0.25%, Sulphur <= 0.045%, Phosphorus <= 0.045%", "category": "Chemical", "mandatory": True},
            {"id": "req-02", "text": "0.2% Proof stress / yield stress conforming to specified grade (e.g. 500 N/mm2 for Fe 500)", "category": "Mechanical", "mandatory": True},
            {"id": "req-03", "text": "Minimum elongation of 16.0% for Fe 500D grades to guarantee seismic ductility", "category": "Mechanical", "mandatory": True},
            {"id": "req-04", "text": "Bend and Re-bend test without surface cracking or rupture", "category": "Mechanical", "mandatory": True}
        ],
        "testing": {
            "duration": "1–3 weeks",
            "labs": 40,
            "keyTests": ["Spectrometric chemical analysis", "Tensile test on UTM", "Bend and rebend test", "Nominal mass / meter measurement", "Rib geometry & transverse deformation test"]
        },
        "certification": {
            "scheme": "Scheme I — Product Certification (ISI Mark)",
            "process": ["Submit application with factory quality plan", "BIS officer factory inspection & audit", "Sample collection for independent testing", "Grant of CM/L licence"]
        },
        "sources": [
            {"title": "Ministry of Steel Quality Control Order", "url": "https://steel.gov.in", "type": "Official Gazette"}
        ]
    },
    {
        "id": "is-4151",
        "number": "IS 4151",
        "title": "Protective Helmets for Riders of Two-Wheeled Motor Vehicles",
        "category": "Automotive & Safety",
        "subcategory": "Protective Equipment",
        "status": "Active",
        "last_updated": "2023-05-15",
        "qco_applicable": True,
        "bis_mark_required": True,
        "scope": "Specifies requirements regarding construction, workmanship, finish, and performance for protective helmets intended for riders of two-wheeled motor vehicles.",
        "overview": "Enforces maximum weight limits (1.2 kg), impact absorption, chin strap retention system strength, peripheral vision angles, and visor optical properties.",
        "requirements": [
            {"id": "req-01", "text": "Maximum helmet weight limit not exceeding 1.2 kg", "category": "Physical", "mandatory": True},
            {"id": "req-02", "text": "Impact absorption test using drop-tower accelerometer at ambient, hot, cold, and wet conditions", "category": "Safety", "mandatory": True},
            {"id": "req-03", "text": "Retention system dynamic test and chin strap slippage <= 10mm", "category": "Mechanical", "mandatory": True},
            {"id": "req-04", "text": "Visor luminous transmittance >= 85% and scratch resistance", "category": "Optical", "mandatory": True}
        ],
        "testing": {
            "duration": "2–4 weeks",
            "labs": 15,
            "keyTests": ["Impact attenuation test", "Retention system dynamic test", "Visor optical clarity test", "Rigidity test"]
        },
        "certification": {
            "scheme": "Scheme I — Product Certification (ISI Mark)",
            "process": ["Mandatory under MoRTH QCO", "Factory audit & batch test records review", "Independent testing at BIS or ICAT/ARAI labs", "Grant of ISI Mark"]
        },
        "sources": [
            {"title": "Ministry of Road Transport & Highways QCO", "url": "https://morth.nic.in", "type": "Official Gazette"}
        ]
    },
    {
        "id": "is-269",
        "number": "IS 269",
        "title": "Ordinary Portland Cement — Specification (33 Grade, 43 Grade, 53 Grade)",
        "category": "Civil & Construction",
        "subcategory": "Cement & Concrete",
        "status": "Active",
        "last_updated": "2023-02-10",
        "qco_applicable": True,
        "bis_mark_required": True,
        "scope": "Covers the manufacture and chemical and physical requirements of ordinary Portland cement of 33, 43, and 53 grades.",
        "overview": "Specifies fineness by specific surface, setting time, soundness by Le-Chatelier method and autoclave test, and compressive strengths at 3, 7, and 28 days.",
        "requirements": [
            {"id": "req-01", "text": "Compressive strength: >= 27 MPa (3-day), >= 37 MPa (7-day), >= 53 MPa (28-day for 53 Grade)", "category": "Mechanical", "mandatory": True},
            {"id": "req-02", "text": "Initial setting time >= 30 minutes; Final setting time <= 600 minutes", "category": "Physical", "mandatory": True},
            {"id": "req-03", "text": "Soundness expansion <= 10mm by Le-Chatelier method", "category": "Physical", "mandatory": True},
            {"id": "req-04", "text": "Insoluble residue <= 5.0%, Magnesia <= 6.0%, Total loss on ignition <= 5.0%", "category": "Chemical", "mandatory": True}
        ],
        "testing": {
            "duration": "28–35 days (due to 28-day curing)",
            "labs": 30,
            "keyTests": ["Compressive strength test", "Fineness test (Blaine method)", "Setting time (Vicat apparatus)", "Soundness autoclave test", "Chemical gravimetric analysis"]
        },
        "certification": {
            "scheme": "Scheme I — Product Certification (ISI Mark)",
            "process": ["Mandatory Cement QCO enforcement", "Factory inspection & in-house lab validation", "Independent sample testing", "Grant of CM/L licence"]
        },
        "sources": [
            {"title": "Cement (Quality Control) Order", "url": "https://dpiit.gov.in", "type": "Official Gazette"}
        ]
    },
    {
        "id": "is-2082",
        "number": "IS 2082",
        "title": "Stationary Storage Type Electric Water Heaters",
        "category": "Electrical Appliances",
        "subcategory": "Water Heating",
        "status": "Active",
        "last_updated": "2023-07-20",
        "qco_applicable": True,
        "bis_mark_required": True,
        "scope": "Specifies safety and performance requirements for stationary storage electric water heaters for household and commercial use.",
        "overview": "Governs standing heat loss, energy efficiency star rating compliance, hydrostatic pressure endurance of the inner tank, thermal cut-outs, and safety valves.",
        "requirements": [
            {"id": "req-01", "text": "Hydrostatic pressure test on inner vessel up to rated test pressure (e.g. 8 bar)", "category": "Pressure", "mandatory": True},
            {"id": "req-02", "text": "Standing heat loss limit (kWh/24h) adhering to energy conservation benchmarks", "category": "Energy", "mandatory": True},
            {"id": "req-03", "text": "Non-self-resetting thermal cut-out operating within safe temperature limits", "category": "Safety", "mandatory": True}
        ],
        "testing": {
            "duration": "3–5 weeks",
            "labs": 20,
            "keyTests": ["Hydrostatic pressure test", "Standing loss test", "Thermal cut-out operation test", "Electric strength test"]
        },
        "certification": {
            "scheme": "Scheme I — Product Certification (ISI Mark)",
            "process": ["Mandatory QCO compliance", "Factory audit & inspection", "BIS lab testing", "CM/L issuance"]
        },
        "sources": [
            {"title": "DPIIT Electrical Appliances QCO", "url": "https://dpiit.gov.in", "type": "Official Gazette"}
        ]
    },
    {
        "id": "is-9873-part-1",
        "number": "IS 9873 (Part 1)",
        "title": "Safety of Toys — Safety Aspects Related to Mechanical and Physical Properties",
        "category": "Consumer Goods & Toys",
        "subcategory": "Toy Safety",
        "status": "Active",
        "last_updated": "2023-01-05",
        "qco_applicable": True,
        "bis_mark_required": True,
        "scope": "Applies to all toys designed or intended for use in play by children under 14 years of age.",
        "overview": "Specifies requirements and test methods for physical hazards, small parts choking hazards, sharp edges, points, cords, and dynamic impact stability.",
        "requirements": [
            {"id": "req-01", "text": "No small parts or detachable choking hazards for toys intended for under 36 months", "category": "Safety", "mandatory": True},
            {"id": "req-02", "text": "Drop test, torque test, and tension test without producing sharp edges", "category": "Mechanical", "mandatory": True},
            {"id": "req-03", "text": "Heavy metal migration limits (Lead, Cadmium, Mercury, Arsenic) as per Part 3", "category": "Chemical", "mandatory": True}
        ],
        "testing": {
            "duration": "2–3 weeks",
            "labs": 22,
            "keyTests": ["Small parts cylinder test", "Sharp edge & sharp point test", "Tension and torque test", "Heavy metal chemical analysis"]
        },
        "certification": {
            "scheme": "Scheme I — Product Certification (ISI Mark)",
            "process": ["Toys (Quality Control) Order mandatory", "Factory audit for domestic/foreign units", "Lab testing", "Grant of ISI Mark"]
        },
        "sources": [
            {"title": "Toys (Quality Control) Order", "url": "https://dpiit.gov.in", "type": "Official Gazette"}
        ]
    }
]

# In-memory runtime cache for dynamically discovered standards via Gemini AI
DYNAMIC_STANDARDS_CACHE: Dict[str, Dict[str, Any]] = {}


class StandardsService:
    @staticmethod
    def _search_curated(query: str, category: Optional[str], status_filter: Optional[str]) -> List[Dict[str, Any]]:
        all_items = list(CURATED_STANDARDS_DB) + list(DYNAMIC_STANDARDS_CACHE.values())
        # Deduplicate by number
        seen = set()
        deduped = []
        for item in all_items:
            num = item.get("number", "").strip().lower()
            if num not in seen:
                seen.add(num)
                deduped.append(item)

        results = deduped
        if query:
            q = query.lower().strip()
            results = [
                s for s in results
                if q in s["number"].lower()
                or q in s["title"].lower()
                or q in s["category"].lower()
                or q in s.get("subcategory", "").lower()
                or q in s.get("scope", "").lower()
            ]
        if category and category != "All Categories":
            results = [s for s in results if s["category"].lower() == category.lower()]
        if status_filter and status_filter != "All Status":
            results = [s for s in results if s["status"].lower() == status_filter.lower()]
        return results

    @staticmethod
    def _discover_standards_via_ai(query: str) -> List[Dict[str, Any]]:
        """
        Use Google Gemini AI to search and identify authentic Indian Standards for any product query.
        """
        prompt = f"What official Indian Standard (IS), testing requirements, Quality Control Order (QCO), and certification scheme apply to '{query}' in India?"

        try:
            res = gemini_service.generate_response(prompt)
            std_info = res.get("applicable_standard") or {}
            ref = std_info.get("reference") or std_info.get("number")
            title = std_info.get("title")

            if not ref or not title:
                return []

            slug_id = re.sub(r'[^a-zA-Z0-9]+', '-', ref).strip('-').lower()
            qco_info = res.get("qco") or {}
            qco_app = qco_info.get("applicable", False) if isinstance(qco_info, dict) else False

            req_list = res.get("requirements", [])
            reqs = [
                {"id": f"req-{i+1:02d}", "text": r, "category": "Safety", "mandatory": True}
                for i, r in enumerate(req_list)
            ] if req_list else [{"id": "req-01", "text": "Conformity to Indian Standard specifications", "category": "General", "mandatory": True}]

            testing_list = res.get("testing", [])
            cert_list = res.get("certification", [])

            std_obj = {
                "id": slug_id,
                "number": ref,
                "title": title,
                "category": std_info.get("applicability", "Indian Standard"),
                "subcategory": query.title(),
                "status": std_info.get("status", "Active"),
                "last_updated": "2023-01-01",
                "qco_applicable": qco_app,
                "bis_mark_required": qco_app or True,
                "scope": std_info.get("applicability") or res.get("summary") or res.get("answer", f"Specifies requirements for {title}."),
                "overview": res.get("answer") or f"Standard specifications and testing protocols for {title}.",
                "requirements": reqs,
                "testing": {
                    "duration": "2–4 weeks",
                    "labs": 15,
                    "keyTests": testing_list if testing_list else ["Safety evaluation", "Type test", "Endurance test"],
                },
                "certification": {
                    "scheme": cert_list[0] if cert_list else "Scheme I — Product Certification (ISI Mark)",
                    "process": cert_list if len(cert_list) > 1 else [
                        "Online application on BIS Manakonline portal",
                        "Factory audit and quality control verification",
                        "Independent sample testing at BIS-recognized lab",
                        "Grant of license to apply Standard Mark"
                    ]
                },
                "sources": [
                    {"title": "Bureau of Indian Standards", "url": "https://www.bis.gov.in", "type": "Official"},
                    {"title": "BIS Manakonline Portal", "url": "https://www.manakonline.in", "type": "Official"}
                ]
            }

            # Cache discovered standard
            DYNAMIC_STANDARDS_CACHE[slug_id] = std_obj
            return [std_obj]
        except Exception as e:
            logger.error(f"Error in AI standards discovery for '{query}': {e}")
            return []

    @staticmethod
    def search_standards(
        query: Optional[str] = None,
        category: Optional[str] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Search and filter standards, dynamically querying Gemini AI for un-indexed search terms."""
        results = StandardsService._search_curated(query or "", category, status_filter)

        # If user searched for a specific query and found 0 results, perform live AI discovery
        if query and len(results) == 0 and len(query.strip()) >= 2:
            ai_discovered = StandardsService._discover_standards_via_ai(query.strip())
            results = ai_discovered

        total = len(results)
        offset = (page - 1) * limit
        paginated = results[offset:offset + limit]

        return {
            "total": total,
            "results": paginated,
            "page": page,
            "limit": limit,
        }

    @staticmethod
    def get_standard_by_id(standard_id: str) -> Dict[str, Any]:
        """Get standard details by ID or IS Number, with dynamic fallback."""
        # Check curated DB
        for s in CURATED_STANDARDS_DB:
            if s["id"] == standard_id or s["number"].lower() == standard_id.lower() or s["id"].lower() == standard_id.lower():
                return s

        # Check dynamic cache
        if standard_id in DYNAMIC_STANDARDS_CACHE:
            return DYNAMIC_STANDARDS_CACHE[standard_id]

        for s in DYNAMIC_STANDARDS_CACHE.values():
            if s["number"].lower() == standard_id.lower():
                return s

        # If not found, dynamically fetch standard info via AI
        ai_res = StandardsService._discover_standards_via_ai(standard_id)
        if ai_res:
            return ai_res[0]

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Standard '{standard_id}' not found in official index.",
        )

    @staticmethod
    def get_saved_standards(db: Session, user: User) -> List[SavedStandard]:
        """Get all saved standards for authenticated user with strict user isolation."""
        return db.query(SavedStandard).filter(
            SavedStandard.user_id == user.id
        ).order_by(desc(SavedStandard.created_at)).all()

    @staticmethod
    def save_standard(db: Session, user: User, req: SaveStandardRequest) -> SavedStandard:
        """Save/bookmark an Indian Standard for authenticated user."""
        existing = db.query(SavedStandard).filter(
            SavedStandard.user_id == user.id,
            SavedStandard.standard_reference == req.standard_reference,
        ).first()

        if existing:
            return existing

        saved = SavedStandard(
            user_id=user.id,
            standard_reference=req.standard_reference,
            title=req.title,
            category=req.category,
            status=req.status,
        )
        db.add(saved)
        db.commit()
        db.refresh(saved)
        return saved

    @staticmethod
    def delete_saved_standard(db: Session, user: User, standard_id: str) -> bool:
        """Delete saved standard with user isolation."""
        saved = db.query(SavedStandard).filter(
            SavedStandard.user_id == user.id,
            (SavedStandard.standard_reference == standard_id) | (SavedStandard.id == standard_id),
        ).first()

        if not saved:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved standard not found.",
            )

        db.delete(saved)
        db.commit()
        return True
