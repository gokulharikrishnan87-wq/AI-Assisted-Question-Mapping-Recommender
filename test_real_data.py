#!/usr/bin/env python3
"""Test local embeddings with real RSC and SLCP data."""

import os
import sys
import json
import openpyxl
from pathlib import Path

# Set environment for local embeddings
os.environ['PROVIDER'] = 'local'
os.environ['EMBEDDING_MODEL_ID'] = 'all-MiniLM-L6-v2'
os.environ['EMBEDDING_DIMENSION'] = '384'

# Add src to path
sys.path.insert(0, 'src')

from mapper_copilot.providers.embeddings import create_embedding_provider_from_settings
from mapper_copilot.providers.llm import MockLLM
from mapper_copilot.providers.vector_store import NumpyVectorStore
from mapper_copilot.core.suggester import Suggester

print("="*70)
print("Testing Local Embeddings with Real RSC and SLCP Data")
print("="*70)
print()

# Load RSC questions
print("Loading RSC questions...")
wb = openpyxl.load_workbook("RSC Questions.xlsx")
ws = wb.active

rsc_questions = []
headers = None
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0:
        headers = row
        continue
    if any(row):
        rsc_questions.append(dict(zip(headers, row)))

print(f"✓ Loaded {len(rsc_questions)} RSC questions")
print()

# Load SLCP questions
print("Loading SLCP questions...")
with open("slcp_data_dictionary.json") as f:
    slcp_data = json.load(f)

slcp_questions = {
    k: v.get("question", "")
    for k, v in slcp_data.items()
    if isinstance(v, dict) and "question" in v and v.get("question", "").strip()
}

print(f"✓ Loaded {len(slcp_questions)} SLCP questions")
print()

# Initialize embedder
print("Initializing local embeddings provider...")
embedder = create_embedding_provider_from_settings()
print(f"✓ Created {type(embedder).__name__}")
print(f"  Model: {embedder.model_name}")
print()

# Build vector store
print("Building vector store with SLCP embeddings...")
print("  (This will take a moment on first run to download the model)")
slcp_texts = list(slcp_questions.values())
slcp_keys = list(slcp_questions.keys())

# Embed in batches for progress
batch_size = 100
all_embeddings = []
for i in range(0, len(slcp_texts), batch_size):
    batch = slcp_texts[i:i+batch_size]
    embeddings = embedder.batch_embed(batch)
    all_embeddings.extend(embeddings)
    print(f"  Embedded {min(i+batch_size, len(slcp_texts))}/{len(slcp_texts)} SLCP questions")

# Build metadata
metadata_list = [
    {"slcp_question": slcp_questions[key], "key": key}
    for key in slcp_keys
]

vector_store = NumpyVectorStore()
vector_store.index(all_embeddings, metadata_list)
print(f"✓ Indexed {len(all_embeddings)} SLCP embeddings")
print()

# Create suggester
suggester = Suggester(
    embedding_provider=embedder,
    llm_provider=MockLLM(),
    vector_store=vector_store,
    top_k=3
)
print("✓ Suggester created")
print()

# Test with first 5 RSC questions
print("="*70)
print("Testing Mappings")
print("="*70)
print()

for i, rsc_q in enumerate(rsc_questions[:5], 1):
    question_text = rsc_q.get("LLL Description", "")
    section = rsc_q.get("Section", "")

    if not question_text:
        continue

    print(f"RSC Question {i}:")
    print(f"  Section: {section}")
    print(f"  Question: {question_text[:100]}...")
    print()

    result = suggester.suggest(question_text)

    print(f"  Best SLCP Match:")
    print(f"    Confidence: {result.confidence:.1%}")
    print(f"    Match: {result.mapped_to[:100]}...")
    print()

    print(f"  Top 3 Candidates:")
    for j, candidate in enumerate(result.source_candidates[:3], 1):
        print(f"    {j}. {candidate[:80]}...")

    print()
    print("-"*70)
    print()

print("="*70)
print("✅ Test Complete!")
print("="*70)
print()
print("Summary:")
print(f"  ✓ Local embeddings working with real data")
print(f"  ✓ {len(rsc_questions)} RSC questions available")
print(f"  ✓ {len(slcp_questions)} SLCP questions indexed")
print(f"  ✓ Semantic matching operational")
print()
print("Next steps:")
print("  - Review the mapping quality above")
print("  - Run full mapping on all RSC questions")
print("  - Export results to CSV")
