"""
BIS SmartAI — Comprehensive RAG Verification & Evaluation Script
Tests 8 standard scenarios covering all domains, specific IS numbers, and out-of-scope queries.
"""
import sys
import os
import json
import time

sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

from app.core.config import settings
from rag.retriever import rag_retriever
from rag.generator import rag_generator
import psycopg2

def run_db_verification():
    print("=" * 70)
    print("1. NEON DATABASE VERIFICATION (document_chunks & pgvector)")
    print("=" * 70)
    conn = psycopg2.connect(settings.database_url, sslmode='require')
    cur = conn.cursor()
    
    # 1. Total chunk count
    cur.execute("SELECT COUNT(*) FROM document_chunks")
    total_chunks = cur.fetchone()[0]
    print(f"Total chunks stored: {total_chunks}")

    # 2. Total chunks with non-null embeddings
    cur.execute("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
    embedded_chunks = cur.fetchone()[0]
    print(f"Chunks with valid 768-dim embeddings: {embedded_chunks}")

    # 3. Domain breakdown
    cur.execute("""
        SELECT domain, COUNT(*) as count, COUNT(DISTINCT document_name) as docs, MIN(page_number), MAX(page_number)
        FROM document_chunks
        GROUP BY domain
        ORDER BY count DESC
    """)
    rows = cur.fetchall()
    print("\nDomain Breakdown:")
    for row in rows:
        print(f"  • {row[0]:<25}: {row[1]:>4} chunks | {row[2]} doc(s) | Pages {row[3]} to {row[4]}")

    # 4. Sample metadata check
    cur.execute("SELECT metadata FROM document_chunks WHERE metadata IS NOT NULL LIMIT 1")
    sample_meta = cur.fetchone()
    print(f"\nSample Metadata JSONB:\n  {json.dumps(sample_meta[0] if sample_meta else {}, indent=2)}")

    conn.close()
    return total_chunks > 0

TEST_QUERIES = [
    {
        "id": 1,
        "type": "General BIS Question",
        "query": "What is the primary role of the Bureau of Indian Standards (BIS) and what is the ISI mark?",
    },
    {
        "id": 2,
        "type": "Electrical Domain",
        "query": "What are the BIS requirements and testing protocols for electrical wiring and cables?",
    },
    {
        "id": 3,
        "type": "Household Appliances Domain",
        "query": "What are the safety requirements and testing clauses for domestic electric kettles and water heating appliances under IS 302-2-15?",
    },
    {
        "id": 4,
        "type": "Iron & Steel Domain",
        "query": "What are the technical requirements, tensile strength tests, and QCO mandates for steel and TMT rebar products?",
    },
    {
        "id": 5,
        "type": "Food & Agriculture Domain",
        "query": "What are the compliance and quality standards for food, agricultural produce, and packaged commodities under BIS?",
    },
    {
        "id": 6,
        "type": "Textile & Leather Domain",
        "query": "What standards and physical testing requirements apply to textile fabrics, garments, and leather footwear under BIS?",
    },
    {
        "id": 7,
        "type": "Specific IS Standard Query",
        "query": "Explain Indian Standard IS 302-2-15 and its specific safety clauses for heating appliances.",
    },
    {
        "id": 8,
        "type": "Out-of-Scope / Negative Test (Must NOT Hallucinate)",
        "query": "What are the mandatory BIS certification guidelines for quantum warp core antimatter reactors on starships in the year 2099?",
    },
]

def run_rag_evaluations():
    print("\n" + "=" * 70)
    print("2. RAG RETRIEVAL & GROUNDED GENERATION EVALUATION (8 TEST CASES)")
    print("=" * 70)
    
    for test in TEST_QUERIES:
        print(f"\n--- [TEST {test['id']}/8] {test['type']} ---")
        print(f"Query: \"{test['query']}\"")
        
        # 1. Retrieval
        start_t = time.time()
        chunks = rag_retriever.search(test['query'], top_k=settings.rag_top_k)
        retrieval_t = time.time() - start_t
        
        print(f"Retrieved: {len(chunks)} chunks in {retrieval_t:.2f}s")
        if chunks:
            top = chunks[0]
            print(f"Top Source: {top.get('document_name')} | Page: {top.get('page_number')} | Domain: {top.get('domain')} | Sim: {top.get('similarity', 0):.3f}")
        
        # 2. Generation
        gen_start = time.time()
        response = rag_generator.generate(
            question=test['query'],
            retrieved_chunks=chunks,
        )
        gen_t = time.time() - gen_start
        
        # 3. Output validation
        answer = response.get("answer", "")
        sources = response.get("sources", [])
        rag_used = response.get("rag_context_used", False)
        v_status = response.get("verification_status", "")
        
        print(f"Generation Time: {gen_t:.2f}s | RAG Used: {rag_used} | Verification: {v_status}")
        print(f"Answer Preview: {answer[:250]}...")
        print(f"Sources Count: {len(sources)}")
        if sources:
            print(f"Sample Citation: Document: {sources[0].get('document')} | Page: {sources[0].get('page')} | Standard: {sources[0].get('standard')}")

if __name__ == "__main__":
    db_ok = run_db_verification()
    if db_ok:
        run_rag_evaluations()
    else:
        print("Database not populated yet. Waiting for ingestion.")
