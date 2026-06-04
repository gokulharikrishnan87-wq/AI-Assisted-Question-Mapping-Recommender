"""
Load real RSC/SLCP data and demonstrate the mapping system.
"""
import openpyxl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mapper_copilot.core.suggester import Suggester
from mapper_copilot.providers.embeddings import HashingEmbedder
from mapper_copilot.providers.llm import MockLLM
from mapper_copilot.providers.vector_store import NumpyVectorStore


def load_slcp_questions():
    """Load SLCP questions from the mapping Excel file."""
    file_path = Path(__file__).parent.parent.parent / "SLCP v1-7-0 to RSC FULL - MACRO template - AC Oct 27 1.xlsm"
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return [], []
    
    print(f"📂 Loading from: {file_path.name}")
    
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    
    slcp_questions = []
    rsc_questions = []
    
    for row_idx, row in enumerate(ws.iter_rows(min_row=5, values_only=True), start=5):
        if not row or not row[0]:
            break
        
        section = row[0]
        rsc_key = row[2]
        rsc_text = row[3]
        slcp_id = row[7]
        slcp_text = row[8]
        
        if slcp_text:
            slcp_questions.append({
                "slcp_id": slcp_id,
                "slcp_question": str(slcp_text).strip(),  # KEY: use "slcp_question"
                "rsc_key": rsc_key,
                "section": section,
            })
        
        if rsc_text and rsc_text not in [q.get("rsc_text") for q in rsc_questions]:
            rsc_questions.append({
                "rsc_key": rsc_key,
                "rsc_text": str(rsc_text).strip(),
                "section": section,
            })
    
    print(f"✓ Loaded {len(slcp_questions)} SLCP questions")
    print(f"✓ Loaded {len(rsc_questions)} unique RSC questions")
    
    return slcp_questions, rsc_questions


def main():
    print("\n" + "=" * 110)
    print("🚀 MAPPER COPILOT - REAL DATA DEMO (820 SLCP Questions)")
    print("=" * 110)
    
    # Load real data
    slcp_questions, rsc_questions = load_slcp_questions()
    
    if not slcp_questions or not rsc_questions:
        print("❌ No data loaded. Exiting.")
        return
    
    # Initialize providers
    print(f"\n⚙️ Initializing system...")
    embedding_provider = HashingEmbedder()
    llm_provider = MockLLM()
    vector_store = NumpyVectorStore()
    
    print(f"   ✓ Embedding Provider: HashingEmbedder (deterministic, offline)")
    print(f"   ✓ LLM Provider: MockLLM (deterministic text generation)")
    print(f"   ✓ Vector Store: NumpyVectorStore (in-memory cosine similarity)")
    
    # Seed vector store with SLCP questions
    print(f"\n📍 Seeding vector store with {len(slcp_questions)} SLCP questions...")
    slcp_texts = [q["slcp_question"] for q in slcp_questions]
    metadata_list = [{"slcp_question": q["slcp_question"], "slcp_id": q["slcp_id"], "section": q.get("section")} for q in slcp_questions]
    
    embeddings = [embedding_provider.embed(text) for text in slcp_texts]
    vector_store.index(embeddings, metadata_list)
    print(f"   ✓ Indexed {len(embeddings)} vectors with metadata")
    
    # Create suggester with the SEEDED vector store
    suggester = Suggester(
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
        vector_store=vector_store,  # USE THE SEEDED STORE
        top_k=3,
    )
    print(f"   ✓ Suggester created (top_k=3)")
    
    # Demo mappings
    print(f"\n🎯 MAPPING REAL RSC QUESTIONS TO SLCP:\n")
    print("=" * 110)
    
    sample_count = 5
    for i, rsc_q in enumerate(rsc_questions[:sample_count]):
        rsc_text = rsc_q["rsc_text"]
        section = rsc_q["section"]
        
        print(f"\n[{i+1}] RSC: {rsc_text[:100]}")
        print(f"    Section: {section}")
        
        try:
            mapping = suggester.suggest(rsc_text)
            
            print(f"\n    ✅ MAPPED TO SLCP:")
            print(f"       • Question: {mapping.mapped_to[:100]}")
            print(f"       • Confidence: {mapping.confidence:.1%}")
            print(f"       • Mapping Rule: {mapping.rule[:100]}")
            print(f"       • Alternative candidates: {len(mapping.source_candidates)}")
            
            if mapping.source_candidates:
                print(f"\n       Top alternatives:")
                for j, cand in enumerate(mapping.source_candidates[:2], 1):
                    print(f"         {j}. {cand[:80]}...")
        except Exception as e:
            import traceback
            print(f"    ❌ Error: {e}")
            traceback.print_exc()
        
        print("-" * 110)
    
    print("\n" + "=" * 110)
    print(f"✅ Demo Complete! Mapped {sample_count} real RSC questions to SLCP equivalents.")
    print("=" * 110 + "\n")


if __name__ == "__main__":
    main()
