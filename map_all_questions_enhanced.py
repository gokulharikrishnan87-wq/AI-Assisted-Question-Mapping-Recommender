#!/usr/bin/env python3
"""Map all RSC questions to SLCP with enhanced metadata - Business-friendly format."""

import os
import sys
import json
import openpyxl
import csv
from datetime import datetime

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
print("RSC to SLCP Question Mapping - Enhanced Business Format")
print("Using Local Sentence-Transformers Embeddings")
print("="*70)
print()

# Load RSC questions
print("📥 Loading RSC questions...")
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

print(f"   ✓ Loaded {len(rsc_questions)} RSC questions")

# Load SLCP questions with full metadata
print("📥 Loading SLCP questions with metadata...")
with open("slcp_data_dictionary.json") as f:
    slcp_data = json.load(f)

# Keep full SLCP data for metadata lookup
slcp_questions = {}
slcp_metadata = {}

for key, value in slcp_data.items():
    if isinstance(value, dict) and "question" in value and value.get("question", "").strip():
        slcp_questions[key] = value.get("question", "")
        slcp_metadata[key] = {
            "key": key,
            "number": value.get("number", ""),
            "section": value.get("section", ""),
            "subsection": value.get("subsection", ""),
            "category": value.get("category", ""),
            "question": value.get("question", "")
        }

print(f"   ✓ Loaded {len(slcp_questions)} SLCP questions with metadata")
print()

# Initialize embedder
print("🧠 Initializing local embeddings provider...")
embedder = create_embedding_provider_from_settings()
print(f"   ✓ Model: {embedder.model_name}")
print()

# Build vector store
print("🔨 Building vector store with SLCP embeddings...")
slcp_texts = list(slcp_questions.values())
slcp_keys = list(slcp_questions.keys())

# Embed in batches
batch_size = 100
all_embeddings = []
for i in range(0, len(slcp_texts), batch_size):
    batch = slcp_texts[i:i+batch_size]
    embeddings = embedder.batch_embed(batch)
    all_embeddings.extend(embeddings)
    progress = min(i+batch_size, len(slcp_texts))
    pct = (progress / len(slcp_texts)) * 100
    print(f"   [{pct:5.1f}%] Embedded {progress}/{len(slcp_texts)} SLCP questions", end='\r')

print(f"\n   ✓ Indexed {len(all_embeddings)} SLCP embeddings")

# Build metadata - include SLCP key in metadata
metadata_list = [
    {"slcp_question": slcp_questions[key], "key": key}
    for key in slcp_keys
]

vector_store = NumpyVectorStore()
vector_store.index(all_embeddings, metadata_list)
print()

# Create suggester with top_k=5
suggester = Suggester(
    embedding_provider=embedder,
    llm_provider=MockLLM(),
    vector_store=vector_store,
    top_k=5  # Get top 5 matches
)
print("✓ Suggester ready (configured for top 5 matches)")
print()

# Map all RSC questions
print("="*70)
print("🔄 Mapping All RSC Questions")
print("="*70)
print()

results = []
errors = []

for i, rsc_q in enumerate(rsc_questions, 1):
    question_text = rsc_q.get("LLL Description", "")
    lll_key = rsc_q.get("LLL Key (unique)", f"RSC_{i}")
    section = rsc_q.get("Section", "")

    if not question_text:
        continue

    try:
        result = suggester.suggest(question_text)

        # Get SLCP metadata for best match
        best_match_meta = slcp_metadata.get(result.source_candidates[0] if result.source_candidates else "", {})

        # Prepare result with enhanced SLCP information
        row = {
            "RSC_Key": lll_key,
            "RSC_Section": section,
            "RSC_Question": question_text,
            "Best_SLCP_Key": best_match_meta.get("key", ""),
            "Best_SLCP_Number": best_match_meta.get("number", ""),
            "Best_SLCP_Section": best_match_meta.get("section", ""),
            "Best_SLCP_Subsection": best_match_meta.get("subsection", ""),
            "Best_SLCP_Question": result.mapped_to,
            "Confidence": result.confidence,
        }

        # Add top 5 alternatives with their metadata
        for j in range(5):
            if j < len(result.source_candidates):
                alt_question = result.source_candidates[j]
                # Find the SLCP key for this alternative
                alt_key = None
                for key, question in slcp_questions.items():
                    if question == alt_question:
                        alt_key = key
                        break

                alt_meta = slcp_metadata.get(alt_key, {}) if alt_key else {}
                row[f"Alt_{j+1}_SLCP_Key"] = alt_meta.get("key", "")
                row[f"Alt_{j+1}_SLCP_Number"] = alt_meta.get("number", "")
                row[f"Alt_{j+1}_SLCP_Section"] = alt_meta.get("section", "")
                row[f"Alt_{j+1}_Question"] = alt_question
            else:
                row[f"Alt_{j+1}_SLCP_Key"] = ""
                row[f"Alt_{j+1}_SLCP_Number"] = ""
                row[f"Alt_{j+1}_SLCP_Section"] = ""
                row[f"Alt_{j+1}_Question"] = ""

        results.append(row)

        # Progress indicator
        pct = (i / len(rsc_questions)) * 100
        print(f"   [{pct:5.1f}%] Mapped {i}/{len(rsc_questions)} questions (Confidence: {result.confidence:.0%})", end='\r')

    except Exception as e:
        errors.append({
            "RSC_Key": lll_key,
            "RSC_Question": question_text,
            "Error": str(e)
        })

print(f"\n   ✓ Completed {len(results)} mappings")
if errors:
    print(f"   ⚠ {len(errors)} errors encountered")
print()

# Export to CSV
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"rsc_slcp_mappings_enhanced_{timestamp}.csv"

print("="*70)
print("💾 Exporting Results")
print("="*70)
print()

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    if results:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

print(f"✅ Saved to: {output_file}")
print()

# Statistics
if results:
    confidences = [r["Confidence"] for r in results]
    avg_confidence = sum(confidences) / len(confidences)
    high_conf = sum(1 for c in confidences if c >= 0.7)
    med_conf = sum(1 for c in confidences if 0.5 <= c < 0.7)
    low_conf = sum(1 for c in confidences if c < 0.5)

    print("📊 Summary Statistics")
    print("="*70)
    print(f"Total Mappings:      {len(results)}")
    print(f"Average Confidence:  {avg_confidence:.1%}")
    print()
    print(f"High Confidence (≥70%):     {high_conf:4d} ({high_conf/len(results)*100:5.1f}%)")
    print(f"Medium Confidence (50-70%): {med_conf:4d} ({med_conf/len(results)*100:5.1f}%)")
    print(f"Low Confidence (<50%):      {low_conf:4d} ({low_conf/len(results)*100:5.1f}%)")
    print("="*70)
    print()

print("📋 CSV Columns:")
print("="*70)
print("RSC Information:")
print("  - RSC_Key: Unique RSC question identifier")
print("  - RSC_Section: RSC section name")
print("  - RSC_Question: Full RSC question text")
print()
print("Best SLCP Match:")
print("  - Best_SLCP_Key: SLCP question key (e.g., 'fp-1')")
print("  - Best_SLCP_Number: SLCP question number (e.g., 'FP-1')")
print("  - Best_SLCP_Section: SLCP section name")
print("  - Best_SLCP_Subsection: SLCP subsection")
print("  - Best_SLCP_Question: Full SLCP question text")
print("  - Confidence: Match confidence score (0-1)")
print()
print("Top 5 Alternatives (for each):")
print("  - Alt_X_SLCP_Key: SLCP key")
print("  - Alt_X_SLCP_Number: SLCP number")
print("  - Alt_X_SLCP_Section: SLCP section")
print("  - Alt_X_Question: Full question text")
print("="*70)
print()

print("✅ All Done!")
print()
print("Next steps:")
print(f"  1. Open {output_file} in Excel/Sheets")
print(f"  2. Review mappings with full SLCP context")
print(f"  3. Use SLCP Key/Number to reference back to source")
print(f"  4. Filter by RSC or SLCP section for analysis")
