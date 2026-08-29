"""
BIS Services API Router
GET /api/services
"""
from typing import List, Optional
from fastapi import APIRouter, Query

router = APIRouter(prefix="/services", tags=["BIS Services Directory"])

BIS_SERVICES_DIRECTORY = [
    {
        "id": "srv-001",
        "name": "Product Certification Scheme (Scheme I - ISI Mark)",
        "category": "Certification",
        "description": "Grant of licence to use or apply the Standard Mark (ISI Mark) on products conforming to relevant Indian Standards.",
        "whoNeedsIt": "Domestic and foreign manufacturers producing goods covered under mandatory Quality Control Orders (QCOs) or voluntary ISI mark certification.",
        "keyProducts": ["Electrical Appliances", "Steel & Iron Products", "Cement", "Automotive Components", "Food & Beverages", "Pipes & Fittings"],
        "process": [
            "Submit online application via BIS Manakonline (manakonline.in)",
            "Preliminary factory audit and inspection by BIS technical officers",
            "Independent sample collection and drawing for testing at BIS-recognized laboratories",
            "Grant of license and allotment of CM/L (Certification Marks Licence) number upon passing conformity assessment"
        ],
        "timeframe": "30 to 60 days from complete application submission",
        "official_url": "https://www.manakonline.in",
        "portal_name": "BIS Manakonline Portal",
        "verification_status": "verified"
    },
    {
        "id": "srv-002",
        "name": "Compulsory Registration Scheme (CRS - Scheme II)",
        "category": "Registration",
        "description": "Self-declaration of conformity registration for electronic and information technology goods as per MeitY and BIS orders.",
        "whoNeedsIt": "Manufacturers and brand owners of IT equipment, consumer electronics, solar modules, smart watches, and battery systems.",
        "keyProducts": ["Laptops & Tablets", "LED Lights & Drivers", "Mobile Phones", "Power Adapters", "Smart Watches", "Inverters"],
        "process": [
            "Test product samples in a BIS-recognized laboratory in India",
            "Obtain test report conforming to applicable IS standard (e.g. IS 13252 / IS 16046)",
            "Submit online application for registration on CRS portal within 90 days of test report",
            "Grant of Registration Number (R-Number) and authorization to apply standard CRS label"
        ],
        "timeframe": "15 to 25 days following test report submission",
        "official_url": "https://www.bis.gov.in/product-certification/compulsory-registration-scheme-crs/",
        "portal_name": "BIS CRS e-Portal",
        "verification_status": "verified"
    },
    {
        "id": "srv-003",
        "name": "Foreign Manufacturers Certification Scheme (FMCS - Scheme I)",
        "category": "Certification",
        "description": "Certification scheme enabling overseas manufacturing units to obtain BIS licence and use the ISI Mark on goods exported to India.",
        "whoNeedsIt": "Overseas manufacturers outside India exporting covered products under Indian QCOs.",
        "keyProducts": ["Chemicals & Petrochemicals", "Steel Products", "Tyres", "Heavy Electrical Machinery", "Toys"],
        "process": [
            "Nominate an Authorized Indian Representative (AIR) residing in India",
            "Submit detailed application with factory quality management system documentation",
            "Physical factory inspection and audit by BIS officers at overseas facility",
            "Witnessing of testing and drawing of independent samples for testing in India",
            "Grant of FMCS licence with annual surveillance audits"
        ],
        "timeframe": "3 to 6 months depending on audit scheduling and testing",
        "official_url": "https://www.bis.gov.in/product-certification/foreign-manufacturers-certification-scheme-fmcs/",
        "portal_name": "BIS FMCS Division",
        "verification_status": "verified"
    },
    {
        "id": "srv-004",
        "name": "Laboratory Recognition Scheme (LRS)",
        "category": "Laboratories",
        "description": "Scheme for recognition of testing and calibration laboratories for conformity assessment of samples under BIS certification schemes.",
        "whoNeedsIt": "Government, academic, and private commercial testing laboratories seeking to test BIS regulatory samples.",
        "keyProducts": ["Testing Laboratories", "NABL Accredited Testing Centers", "Calibration Facilities"],
        "process": [
            "Obtain NABL accreditation as per ISO/IEC 17025 for relevant testing scopes",
            "Submit application on BIS Laboratory Recognition portal",
            "Technical evaluation and assessment audit by BIS assessment team",
            "Inclusion in the official BIS Directory of Recognized Laboratories"
        ],
        "timeframe": "45 to 60 days",
        "official_url": "https://www.bis.gov.in/laboratory-services/laboratory-recognition-scheme-lrs/",
        "portal_name": "BIS Laboratory Management",
        "verification_status": "verified"
    },
    {
        "id": "srv-005",
        "name": "Hallmarking Scheme (Gold & Silver)",
        "category": "Hallmarking",
        "description": "Accurate determination and official recording of the proportionate content of precious metal in gold and silver jewellery / artefacts.",
        "whoNeedsIt": "Jewellers and Assaying & Hallmarking Centres (AHC) across mandatory hallmarking districts in India.",
        "keyProducts": ["Gold Jewellery (14K, 18K, 20K, 22K, 23K, 24K)", "Silver Artefacts & Bullion"],
        "process": [
            "Jeweller registers online via Manakonline portal",
            "Articles submitted to BIS-recognized Assaying & Hallmarking Centre",
            "Assay testing (XRF / Fire Assay) to verify karat purity",
            "Laser engraving of HUID (Hallmark Unique Identification) 6-digit alphanumeric code"
        ],
        "timeframe": "Instant registration for jewellers; same-day hallmarking at AHC",
        "official_url": "https://www.manakonline.in",
        "portal_name": "BIS Hallmarking Portal",
        "verification_status": "verified"
    },
    {
        "id": "srv-006",
        "name": "Management Systems Certification (MSCD)",
        "category": "Management Systems",
        "description": "Certification of organization quality and safety management systems according to international and national standards.",
        "whoNeedsIt": "Enterprises, manufacturers, service providers, and public institutions seeking accredited quality certifications.",
        "keyProducts": ["ISO 9001 (QMS)", "ISO 14001 (EMS)", "ISO 22000 (FSMS)", "ISO 45001 (OHSMS)", "ISO 27001 (ISMS)"],
        "process": [
            "Submit application along with Quality Manual and documented procedures",
            "Stage 1 readiness assessment audit by BIS lead auditors",
            "Stage 2 certification audit of operational processes",
            "Issuance of Management System Certificate valid for 3 years"
        ],
        "timeframe": "30 to 45 days",
        "official_url": "https://www.bis.gov.in/management-system-certification/",
        "portal_name": "BIS MSCD Division",
        "verification_status": "verified"
    }
]


@router.get("")
def get_services(category: Optional[str] = Query(None, description="Filter by service category")):
    """Get all BIS service schemes and procedures."""
    if category and category != "All Categories":
        return [s for s in BIS_SERVICES_DIRECTORY if s["category"].lower() == category.lower()]
    return BIS_SERVICES_DIRECTORY
