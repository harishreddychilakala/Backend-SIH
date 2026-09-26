"""
Test Suite for Consumer-Related Queries & BIS Hallmarking Guidance
Validates:
1. API Endpoints (Standards & Services)
2. Consumer Queries (ISI identification, licence verification, fake mark grievance reporting)
3. Hallmarking Queries (Gold & silver standards, 3-sign hallmark, HUID verification, differences)
4. Source citations, official portals, and guardrails
"""
import sys
import json
import requests

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app.services.gemini_service import gemini_service
from app.services.standards_service import StandardsService

BASE_URL = "http://127.0.0.1:8000"

def test_standards_api():
    print("\n--- 1. Testing Standards API for Hallmarking & Consumer Standards ---")
    # Test IS 1417 (Gold Hallmarking)
    res_gold = StandardsService.get_standard_by_id("is-1417-2016")
    assert res_gold is not None, "IS 1417 should exist in standards database"
    assert "Gold" in res_gold["title"]
    assert "HUID" in json.dumps(res_gold)
    print("[PASS] IS 1417:2016 (Gold Hallmarking) retrieved successfully")

    # Test IS 2112 (Silver Hallmarking)
    res_silver = StandardsService.get_standard_by_id("is-2112-2014")
    assert res_silver is not None
    assert "Silver" in res_silver["title"]
    print("[PASS] IS 2112:2014 (Silver Hallmarking) retrieved successfully")

    # Test IS 14543 (Packaged Water)
    res_water = StandardsService.get_standard_by_id("is-14543-2016")
    assert res_water is not None
    assert "Packaged Drinking Water" in res_water["title"]
    print("[PASS] IS 14543:2016 (Packaged Water) retrieved successfully")

def test_services_api():
    print("\n--- 2. Testing Services API for Hallmarking & Consumer Categories ---")
    r = requests.get(f"{BASE_URL}/api/services")
    assert r.status_code == 200
    services = r.json()
    
    categories = {s["category"] for s in services}
    assert "Hallmarking" in categories, "Hallmarking category must be in services"
    assert "Consumer Services" in categories, "Consumer Services category must be in services"

    hallmark_srv = next(s for s in services if s["category"] == "Hallmarking")
    assert "HUID" in hallmark_srv["description"] or "HUID" in json.dumps(hallmark_srv)
    print(f"[PASS] Hallmarking Scheme verified: {hallmark_srv['name']}")

    consumer_srv = next(s for s in services if s["category"] == "Consumer Services")
    assert "BIS Care" in consumer_srv["name"] or "BIS Care" in consumer_srv["description"]
    print(f"[PASS] Consumer Services verified: {consumer_srv['name']}")

def test_consumer_queries():
    print("\n--- 3. Testing Consumer-Related AI Intelligence ---")
    # Query 1: How to identify BIS certified products & verify licence
    prompt1 = "How can a consumer identify genuine BIS certified products, and how can they verify the licence on the BIS Care App?"
    res1 = gemini_service.generate_response(prompt1)
    ans1 = res1.get("answer", "")
    print(f"Query 1: '{prompt1}'")
    print(f"Response Summary / Preview: {ans1[:250]}...\n")
    assert any(term in ans1.lower() for term in ["isi", "cm/l", "bis care", "licence", "license"]), "Response must mention ISI/CML/BIS Care"
    assert "sources" in res1 and len(res1["sources"]) > 0, "Response must include official sources"
    print("[PASS] Consumer product identification & licence verification response passed!")

    # Query 2: What to do if product has fake ISI mark / sub-standard
    prompt2 = "What should a consumer do if they purchase a product with a fake or falsely labelled ISI mark?"
    res2 = gemini_service.generate_response(prompt2)
    ans2 = res2.get("answer", "")
    print(f"Query 2: '{prompt2}'")
    print(f"Response Summary / Preview: {ans2[:250]}...\n")
    assert any(term in ans2.lower() for term in ["complaint", "grievance", "bis care", "1915", "helpline", "e-daakhil"]), "Response must detail grievance channels"
    print("[PASS] Consumer complaint and fake mark grievance redressal response passed!")

def test_hallmarking_queries():
    print("\n--- 4. Testing Hallmarking & HUID AI Intelligence ---")
    # Query 3: Gold hallmarking 3 signs and HUID verification
    prompt3 = "What are the mandatory 3 signs of gold hallmarking in India, and how do I verify the 6-digit HUID code?"
    res3 = gemini_service.generate_response(prompt3)
    ans3 = res3.get("answer", "")
    print(f"Query 3: '{prompt3}'")
    print(f"Response Summary / Preview: {ans3[:250]}...\n")
    assert any(term in ans3.lower() for term in ["huid", "bis logo", "purity", "22k916", "bis care"]), "Response must explain 3 signs and HUID"
    print("[PASS] Gold hallmarking 3-sign and HUID verification test passed!")

    # Query 4: Difference between Hallmarking and ISI mark
    prompt4 = "Explain the difference between BIS Hallmarking and BIS Product Certification (ISI Mark)."
    res4 = gemini_service.generate_response(prompt4)
    ans4 = res4.get("answer", "")
    print(f"Query 4: '{prompt4}'")
    print(f"Response Summary / Preview: {ans4[:250]}...\n")
    assert "precious" in ans4.lower() or "gold" in ans4.lower() or "jewellery" in ans4.lower(), "Must explain precious metals vs manufactured goods"
    print("[PASS] Hallmarking vs ISI mark distinction test passed!")

def test_ambiguous_and_guardrails():
    print("\n--- 5. Testing Ambiguous Query & Authenticity Guardrail ---")
    prompt5 = "Is my 22k gold bangle with code XY99ZZ definitely 100% genuine pure gold?"
    res5 = gemini_service.generate_response(prompt5)
    ans5 = res5.get("answer", "")
    print(f"Query 5: '{prompt5}'")
    print(f"Response Summary / Preview: {ans5[:250]}...\n")
    # Must instruct user to verify via BIS Care App rather than making unsubstantiated claims
    assert "bis care" in ans5.lower() or "verify" in ans5.lower() or "huid" in ans5.lower(), "System must direct user to verify via BIS Care App HUID lookup"
    print("[PASS] Authenticity guardrail test passed!")

if __name__ == "__main__":
    try:
        test_standards_api()
        test_services_api()
        test_consumer_queries()
        test_hallmarking_queries()
        test_ambiguous_and_guardrails()
        print("\n[SUCCESS] ALL CONSUMER & HALLMARKING TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
