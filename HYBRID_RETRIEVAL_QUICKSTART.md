# Hybrid Retrieval Quick Start Guide

## TL;DR

The Mapper Copilot now uses **hybrid retrieval** (dense embeddings + BM25 keywords) with optional **cross-encoder reranking** for better matching accuracy, especially on questions with specific numbers and codes.

---

## Installation

**Install dependencies:**
```bash
# Install rank-bm25 (required for hybrid retrieval)
pip install rank-bm25

# For local embeddings + cross-encoder reranking (recommended for offline use)
pip install 'mapper-copilot[local-embeddings]'

# For optional LLM reranker (uses Anthropic Claude API)
pip install 'mapper-copilot[llm-reranker]'
```

---

## Configuration

### Option 1: Full Offline (Recommended)
**Best for**: Offline use, no API costs, good quality

Edit `.env`:
```bash
# Use local sentence-transformers models
PROVIDER=local
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2

# Hybrid retrieval settings
K_RETRIEVE=40
USE_BM25=true
SECTION_PRIOR_WEIGHT=0.1

# Local cross-encoder reranker (offline)
RERANKER=local
CROSS_ENCODER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

### Option 2: Hybrid with Claude Reranker
**Best for**: Maximum accuracy, willing to use API

Edit `.env`:
```bash
# Use local models for retrieval
PROVIDER=local
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2

# Hybrid retrieval
K_RETRIEVE=40
USE_BM25=true

# Claude API for reranking (best quality)
RERANKER=llm
RERANKER_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

### Option 3: Dense-Only (Legacy)
**Best for**: Simple setup, semantic matching only

Edit `.env`:
```bash
PROVIDER=local
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2

# Disable BM25 and reranking
USE_BM25=false
RERANKER=none
```

---

## Running the UI

**Start the Streamlit UI:**
```bash
streamlit run src/mapper_copilot/ui.py
```

The UI will automatically:
1. Load SLCP questions from `slcp_data_dictionary.json`
2. Build BM25 index + vector store
3. Initialize hybrid retriever + optional reranker
4. Map RSC questions using the full pipeline

---

## How It Improves Matching

### Problem: Dense-Only Misses Exact Matches

**RSC Question**: "Are workers at least 18 years old?"

**Dense-only retrieval** (semantic similarity):
- Ranks "workers 15 years old" and "workers 18 years old" similarly
- Can't distinguish the specific number

**Hybrid retrieval** (dense + BM25):
- BM25 boosts exact match on "18"
- Dense provides semantic context
- RRF fusion combines both signals
- **Result**: "18 years" ranks higher than "15 years" ✅

### Problem: Missing Specific Codes

**RSC Question**: "Does the facility comply with FP-STE-1?"

**Dense-only**:
- Might match any facility profile question
- Code "FP-STE-1" is lost in embedding

**Hybrid + BM25**:
- BM25 matches exact code "FP-STE-1"
- Ranks that question at the top
- **Result**: Exact code match ✅

---

## API Changes (Backward Compatible)

### Old Code (still works)
```python
from mapper_copilot.core.suggester import Suggester

suggester = Suggester(embedder, llm, vector_store, top_k=5)
result = suggester.suggest("Does the facility have a license?")
```

### New Code (with metadata for better retrieval)
```python
from mapper_copilot.core.suggester import Suggester
from mapper_copilot.providers.retrieval import HybridRetriever, BM25Index
from mapper_copilot.providers.rerankers import create_reranker_from_settings

# Build hybrid retriever
retriever = HybridRetriever(
    embedding_provider=embedder,
    vector_store=vector_store,
    bm25_index=bm25_index,
    k_retrieve=40,
    use_bm25=True,
)

# Optional reranker
reranker = create_reranker_from_settings()

# Create suggester with hybrid retrieval
suggester = Suggester(
    embedding_provider=embedder,
    llm_provider=llm,
    retriever=retriever,
    reranker=reranker,
    top_k=5,
)

# Call with RSC metadata for better matching
rsc_metadata = {
    "section": "1. Business Ethics",
    "lll_key": "1.01",
    "reference_data": "Facility must have valid permits"
}
result = suggester.suggest("Does the facility have a license?", rsc_metadata)
```

---

## Configuration Parameters

### K_RETRIEVE (default: 40)
- Number of candidates to retrieve from hybrid search
- Higher = more candidates to choose from, slower
- Recommended: 40 (good balance)

### USE_BM25 (default: true)
- Enable BM25 lexical matching
- Set to `false` for dense-only (legacy behavior)
- Recommended: `true` (improves number/code matching)

### SECTION_PRIOR_WEIGHT (default: 0.1)
- Weight for boosting same-section candidates
- Range: 0.0 (no boost) to 1.0 (strong boost)
- Recommended: 0.1 (soft boost, not a hard filter)

### RERANKER (default: none)
- `none`: No reranking (use hybrid scores directly)
- `local`: Cross-encoder reranker (offline, requires sentence-transformers)
- `llm`: Claude API reranker (best quality, requires API key)

### CROSS_ENCODER_MODEL (default: cross-encoder/ms-marco-MiniLM-L-6-v2)
- Model for local reranker
- Alternatives:
  - `cross-encoder/ms-marco-MiniLM-L-6-v2` (fast, 80MB)
  - `BAAI/bge-reranker-base` (better quality, 300MB)

---

## Performance Guide

### Speed vs Quality Tradeoff

| Configuration | Speed | Quality | Memory | Offline |
|---------------|-------|---------|--------|---------|
| Dense-only | ⚡⚡⚡ Fast (10ms) | 🟡 Good | 50MB | ✅ |
| Hybrid (dense + BM25) | ⚡⚡ Medium (15ms) | 🟢 Better | 70MB | ✅ |
| Hybrid + local reranker | ⚡ Slower (50ms) | 🟢🟢 Best | 150MB | ✅ |
| Hybrid + LLM reranker | 🐌 Slow (500ms) | 🟢🟢🟢 Excellent | 70MB | ❌ |

**Recommendation for production**:
- Single queries: Hybrid + local reranker
- Batch mapping: Hybrid only (skip reranker for speed)
- Offline requirement: Hybrid + local reranker

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'rank_bm25'"
```bash
pip install rank-bm25
```

### "sentence-transformers not installed" (for local reranker)
```bash
pip install 'mapper-copilot[local-embeddings]'
```

### BM25 not improving results
- Check that `USE_BM25=true` in `.env`
- Verify RSC metadata includes codes/numbers in `reference_data`
- Try increasing `K_RETRIEVE` (e.g., 60)

### Slow performance
- Disable reranker: `RERANKER=none`
- Or reduce `K_RETRIEVE` from 40 to 20
- For batch jobs, run without reranker

### Want to see BM25 scores
Enable debug logging in `.env`:
```bash
LOG_LEVEL=DEBUG
```

Then check logs for:
```
INFO - Retrieved 40 fused candidates (dense + BM25)
```

---

## Examples

### Example 1: Number-Sensitive Question

**Input**:
```python
rsc_metadata = {
    "section": "2. Labor Standards",
    "lll_key": "2.01",
    "reference_data": "Minimum age 18 years"
}
result = suggester.suggest("Are workers at least 18 years old?", rsc_metadata)
```

**Expected**: SLCP question "Are workers at least 18 years old?" ranks higher than "15 years" due to BM25 matching "18".

### Example 2: Code Matching

**Input**:
```python
rsc_metadata = {
    "section": "3. Facility Profile",
    "lll_key": "3.05",
    "reference_data": "FP-STE-1 compliance required"
}
result = suggester.suggest("Does the facility comply with FP-STE-1?", rsc_metadata)
```

**Expected**: SLCP question with code "FP-STE-1" in `number` field ranks at top due to BM25 exact match.

### Example 3: Section Boosting

**Input**:
```python
rsc_metadata = {
    "section": "1. Business Ethics",  # Maps to "MANAGEMENT SYSTEMS" in SLCP
    "lll_key": "1.01",
    "reference_data": ""
}
result = suggester.suggest("Does the facility have an ethics policy?", rsc_metadata)
```

**Expected**: SLCP questions from "MANAGEMENT SYSTEMS" section get soft boost, but other relevant sections can still rank high.

---

## Validation

**Test the system:**
```bash
# Run hybrid retrieval tests
python -m pytest tests/test_retrieval.py -v

# Run integration tests
python -m pytest tests/test_suggester.py::TestHybridRetrieval -v

# Test on real data
streamlit run src/mapper_copilot/ui.py
```

---

## Migration from Dense-Only

**No code changes required!** The system automatically:
1. Detects if `retriever` is provided to `Suggester`
2. Uses hybrid path if available
3. Falls back to legacy dense-only if not

**To enable hybrid**:
1. Update `.env` with new settings (see Configuration section)
2. Restart the UI - it will automatically use hybrid retrieval
3. No code changes needed

---

## Need Help?

- **Documentation**: See `HYBRID_RETRIEVAL_COMPLETE.md` for full technical details
- **Tests**: Check `tests/test_retrieval.py` for usage examples
- **Config**: Review `.env.example` for all available settings

**Common issues**:
- Slow performance? Disable reranker or reduce `K_RETRIEVE`
- Not matching numbers? Ensure `USE_BM25=true`
- Import errors? Install optional dependencies: `pip install 'mapper-copilot[local-embeddings]'`
