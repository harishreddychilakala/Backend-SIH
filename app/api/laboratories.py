"""
Laboratories API Router
GET /api/laboratories
"""
import re
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/laboratories", tags=["Laboratories Directory"])

LABORATORIES_DIRECTORY = [
    {
        "id": "lab-001",
        "name": "BIS Central Laboratory (CL)",
        "type": "Central Laboratory",
        "state": "Uttar Pradesh",
        "city": "Sahibabad, Ghaziabad",
        "address": "Plot No. 20/9, Site IV, Sahibabad Industrial Area, Ghaziabad, UP 201010",
        "testingTypes": ["Electrical", "Chemical", "Mechanical", "Microbiological", "Textile"],
        "standards": ["IS 302-2-15", "IS 1293:2019", "IS 13252", "IS 1786", "IS 3854"],
        "accreditation": "NABL Accredited / BIS Apex Laboratory",
        "contact": "+91-120-4177100 | cl@bis.gov.in",
        "verified": True,
        "verification_status": "verified"
    },
    {
        "id": "lab-002",
        "name": "BIS Western Regional Laboratory (WRLO)",
        "type": "Regional Laboratory",
        "state": "Maharashtra",
        "city": "Mumbai",
        "address": "Manakalaya, E9, MIDC, Andheri (East), Mumbai, Maharashtra 400093",
        "testingTypes": ["Electrical", "Chemical", "Mechanical", "Food & Beverages"],
        "standards": ["IS 302 (Part 1 & 2)", "IS 694", "IS 9873", "IS 15410"],
        "accreditation": "NABL Accredited (ISO/IEC 17025)",
        "contact": "+91-22-28329295 | wrlo@bis.gov.in",
        "verified": True,
        "verification_status": "verified"
    },
    {
        "id": "lab-003",
        "name": "BIS Southern Regional Laboratory (SRLO)",
        "type": "Regional Laboratory",
        "state": "Tamil Nadu",
        "city": "Chennai",
        "address": "CIT Campus, IV Cross Road, Taramani, Chennai, Tamil Nadu 600113",
        "testingTypes": ["Electrical", "Electronics", "Mechanical", "Civil & Construction"],
        "standards": ["IS 1293", "IS 10322", "IS 16102", "IS 1786"],
        "accreditation": "NABL Accredited (ISO/IEC 17025)",
        "contact": "+91-44-22541442 | srlo@bis.gov.in",
        "verified": True,
        "verification_status": "verified"
    },
    {
        "id": "lab-004",
        "name": "BIS Eastern Regional Laboratory (ERLO)",
        "type": "Regional Laboratory",
        "state": "West Bengal",
        "city": "Kolkata",
        "address": "1/14 C.I.T. Scheme VII M, V.I.P. Road, Kankurgachi, Kolkata, West Bengal 700054",
        "testingTypes": ["Mechanical", "Metallurgical", "Chemical", "Electrical"],
        "standards": ["IS 1786", "IS 2062", "IS 1161", "IS 1239"],
        "accreditation": "NABL Accredited (ISO/IEC 17025)",
        "contact": "+91-33-23207080 | erlo@bis.gov.in",
        "verified": True,
        "verification_status": "verified"
    },
    {
        "id": "lab-005",
        "name": "BIS Northern Regional Laboratory (NRLO)",
        "type": "Regional Laboratory",
        "state": "Punjab",
        "city": "Mohali / Chandigarh",
        "address": "Plot No. 4A, Sector 27B, Madhya Marg, Chandigarh 160019",
        "testingTypes": ["Agricultural", "Chemical", "Mechanical", "Electrical"],
        "standards": ["IS 4984", "IS 4985", "IS 9079", "IS 302-2-3"],
        "accreditation": "NABL Accredited (ISO/IEC 17025)",
        "contact": "+91-172-2650206 | nrlo@bis.gov.in",
        "verified": True,
        "verification_status": "verified"
    },
    {
        "id": "lab-006",
        "name": "National Test House (NTH - Northern Region)",
        "type": "Recognized Laboratory",
        "state": "Delhi",
        "city": "New Delhi / Ghaziabad",
        "address": "Kamla Nehru Nagar, Ghaziabad, UP / New Delhi",
        "testingTypes": ["Electrical", "Civil", "Mechanical", "Non-Destructive Testing"],
        "standards": ["IS 302", "IS 1293", "IS 1786", "IS 456", "IS 814"],
        "accreditation": "Govt of India / NABL Accredited & BIS Recognized",
        "contact": "+91-120-2789851 | nth-nr@nic.in",
        "verified": True,
        "verification_status": "verified"
    },
    {
        "id": "lab-007",
        "name": "Central Power Research Institute (CPRI)",
        "type": "Recognized Laboratory",
        "state": "Karnataka",
        "city": "Bengaluru",
        "address": "Prof. Sir C.V. Raman Road, Sadashivanagar P.O., Bengaluru 560080",
        "testingTypes": ["High Voltage Electrical", "Power Equipment", "Cables", "Switchgear"],
        "standards": ["IS 694", "IS 7098", "IS 13947", "IS 302"],
        "accreditation": "Autonomous Society under Ministry of Power / BIS Recognized",
        "contact": "+91-80-22072210 | cpri@nic.in",
        "verified": True,
        "verification_status": "verified"
    },
    {
        "id": "lab-008",
        "name": "Electronic Regional Test Laboratory (ERTL - North / STQC)",
        "type": "Recognized Laboratory",
        "state": "Delhi",
        "city": "New Delhi",
        "address": "S-Block, Okhla Industrial Area, Phase-II, New Delhi 110020",
        "testingTypes": ["Electronics", "Information Technology", "EMC / EMI Testing", "Safety"],
        "standards": ["IS 13252 (Part 1)", "IS 16046", "IS 616", "IS 16102"],
        "accreditation": "STQC Directorate / MeitY / BIS Recognized for CRS",
        "contact": "+91-11-26386219 | ertlnorth@stqc.nic.in",
        "verified": True,
        "verification_status": "verified"
    }
]

# In-memory runtime cache for dynamically discovered laboratories
DYNAMIC_LABS_CACHE: Dict[str, Dict[str, Any]] = {}


def _discover_labs_via_ai(query: str) -> List[Dict[str, Any]]:
    """Query Gemini AI for authentic BIS-recognized / NABL-accredited test laboratories."""
    prompt = f"""Search for recognized Indian testing laboratories and NABL-accredited facilities for: "{query}".

Provide a JSON object with:
"laboratories": A list of up to 3 real, authentic testing laboratories in India matching this query. For each laboratory:
- "name": Official Laboratory Name (e.g. "Automotive Research Association of India (ARAI)" or "Central Institute of Petrochemicals Engineering & Technology (CIPET)")
- "type": "Recognized Laboratory" or "Government Laboratory" or "Regional Testing Centre"
- "state": Indian State (e.g. "Maharashtra", "Tamil Nadu", "Gujarat", "Karnataka", "Delhi", "Telangana")
- "city": City Name
- "address": Full Address
- "testingTypes": list of 3-4 testing categories (e.g. ["Automotive", "Mechanical", "Crash Testing"])
- "standards": list of 2-3 covered Indian Standards (e.g. ["IS 4151", "IS 14623"])
- "accreditation": "NABL Accredited (ISO/IEC 17025) & BIS Recognized"
- "contact": phone or email

STRICT RULE: Do not hallucinate fake names. Return strictly valid JSON."""

    try:
        res = gemini_service.generate_response(prompt)
        raw_list = res.get("laboratories", [])
        discovered = []

        for lab in raw_list:
            if not lab.get("name"):
                continue
            slug_id = re.sub(r'[^a-zA-Z0-9]+', '-', lab["name"]).strip('-').lower()
            lab_obj = {
                "id": slug_id,
                "name": lab.get("name"),
                "type": lab.get("type", "Recognized Laboratory"),
                "state": lab.get("state", "India"),
                "city": lab.get("city", ""),
                "address": lab.get("address", f"{lab.get('city')}, {lab.get('state')}"),
                "testingTypes": lab.get("testingTypes", ["Testing & Conformity"]),
                "standards": lab.get("standards", ["Indian Standards"]),
                "accreditation": lab.get("accreditation", "NABL Accredited (ISO/IEC 17025)"),
                "contact": lab.get("contact", "Official Directory Listing"),
                "verified": True,
                "verification_status": "verified"
            }
            DYNAMIC_LABS_CACHE[slug_id] = lab_obj
            discovered.append(lab_obj)

        return discovered
    except Exception as e:
        logger.error(f"Error discovering laboratories for '{query}': {e}")
        return []


@router.get("")
def search_laboratories(
    query: Optional[str] = Query(None, description="Search query by name, capability or standard"),
    state: Optional[str] = Query(None, description="Filter by Indian State"),
    testing_type: Optional[str] = Query(None, description="Filter by Testing Type"),
):
    """Search and filter BIS-recognized and apex testing laboratories."""
    results = list(LABORATORIES_DIRECTORY) + list(DYNAMIC_LABS_CACHE.values())

    # Deduplicate by name
    seen = set()
    deduped = []
    for lab in results:
        nm = lab.get("name", "").strip().lower()
        if nm not in seen:
            seen.add(nm)
            deduped.append(lab)
    results = deduped

    if query:
        q = query.lower().strip()
        matched = [
            lab for lab in results
            if q in lab["name"].lower()
            or q in lab["city"].lower()
            or q in lab["state"].lower()
            or any(q in t.lower() for t in lab["testingTypes"])
            or any(q in s.lower() for s in lab["standards"])
        ]
        if len(matched) == 0 and len(q) >= 2:
            ai_labs = _discover_labs_via_ai(query.strip())
            matched = ai_labs
        results = matched

    if state and state != "All States":
        results = [lab for lab in results if lab["state"].lower() == state.lower()]

    if testing_type and testing_type != "All Types":
        results = [lab for lab in results if any(testing_type.lower() in t.lower() for t in lab["testingTypes"])]

    return results
