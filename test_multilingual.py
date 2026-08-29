import sys
import os
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

from rag.retriever import rag_retriever
from app.services.chat_service import _generate_ai_response

test_queries = [
    ("Hindi", "घरेलू रूम हीटर के लिए कौन सा BIS मानक और सुरक्षा परीक्षण आवश्यक हैं?"),
    ("Telugu", "స్టీల్ TMT రీబార్ల కొరకు BIS ప్రమాణాలు మరియు QCO నిబంధనలు ఏమిటి?"),
    ("Tamil", "காபி தூள் தயாரிப்புக்கான இந்திய தரம் (BIS Standard) எது?"),
]

for lang, q in test_queries:
    print(f"\n======================================")
    print(f"Testing {lang} Query: {q}")
    chunks = rag_retriever.search(q, top_k=3)
    print(f"Retrieved {len(chunks)} chunks:")
    for c in chunks:
        print(f"  • Doc: {c.get('document_name')} | Page: {c.get('page_number')} | Std: {c.get('standard_number')} | Sim: {c.get('similarity', 0):.3f}")
    
    resp = _generate_ai_response(q)
    print(f"\nAI Response ({lang}) preview:")
    print(resp.get("answer", "")[:300] + "...")
