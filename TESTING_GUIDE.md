# Testing Guide: Local Embedding Provider

This guide shows you how to test the new local sentence-transformers embedding provider.

## Prerequisites

```bash
# Install the package with local embeddings support
pip install -e ".[local-embeddings]"

# Or just the dependencies
pip install sentence-transformers
```

## Quick Tests (5 minutes)

### 1. Quick Sanity Check

```bash
python3 -c "
from mapper_copilot.providers.embeddings import SentenceTransformerEmbedder
embedder = SentenceTransformerEmbedder('all-MiniLM-L6-v2')
emb = embedder.embed('test')
print(f'✅ Works! Shape: {emb.shape}, dtype: {emb.dtype}')
"
```

Expected output:
```
✅ Works! Shape: (384,), dtype: float32
```

### 2. Run Automated Tests

```bash
# Run all embedding tests
pytest tests/test_embeddings.py -v

# Should see: 35 passed (29 passed, 6 skipped if sentence-transformers not installed)
```

### 3. Interactive Test Script

```bash
chmod +x test_embeddings_interactive.py
./test_embeddings_interactive.py
```

This tests:
- ✅ Single embeddings
- ✅ Batch embeddings
- ✅ Semantic similarity
- ✅ Both mock and local providers

## API Testing (10 minutes)

### Option A: Manual API Test

```bash
# Terminal 1: Start API with local embeddings
export PROVIDER=local
export EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
uvicorn mapper_copilot.api:app --reload

# Terminal 2: Test endpoints
curl -X POST http://localhost:8000/suggest \
  -H "Content-Type: application/json" \
  -d '{"rsc_question": "Do workers have safety equipment?"}'
```

### Option B: Automated API Test

```bash
chmod +x test_local_api.sh
./test_local_api.sh
```

This automatically:
1. Creates test configuration
2. Starts API server
3. Tests all endpoints
4. Cleans up

## UI Testing (5 minutes)

```bash
chmod +x test_ui_with_local.sh
./test_ui_with_local.sh
```

Then:
1. Open browser to http://localhost:8501
2. Click "🚀 Start Mapping All Questions"
3. Verify mappings are generated with confidence scores

## Provider Comparison Test

Create a test file to compare all providers:

```python
# test_compare_providers.py
import os
import time
import numpy as np
from mapper_copilot.providers.embeddings import create_embedding_provider

test_text = "Do workers have safety equipment?"

for provider in ['mock', 'local']:
    print(f"\n{'='*50}")
    print(f"Testing {provider.upper()} provider")
    print('='*50)

    if provider == 'local':
        embedder = create_embedding_provider('local', 'all-MiniLM-L6-v2')
    else:
        embedder = create_embedding_provider('mock', embedding_dim=384)

    # Time the embedding
    start = time.time()
    emb = embedder.embed(test_text)
    elapsed = time.time() - start

    print(f"Embedder: {type(embedder).__name__}")
    print(f"Shape: {emb.shape}")
    print(f"Dtype: {emb.dtype}")
    print(f"Norm: {np.linalg.norm(emb):.4f}")
    print(f"Time: {elapsed*1000:.2f}ms")

    # Test semantic similarity (only meaningful for local)
    if provider == 'local':
        q1 = "Do workers wear protective equipment?"
        q2 = "Is safety gear provided?"
        q3 = "What are working hours?"

        e1 = embedder.embed(q1)
        e2 = embedder.embed(q2)
        e3 = embedder.embed(q3)

        print(f"\nSemantic Similarity:")
        print(f"  Similar questions: {np.dot(e1, e2):.4f}")
        print(f"  Different questions: {np.dot(e1, e3):.4f}")
```

Run it:
```bash
python test_compare_providers.py
```

## Configuration Testing

Test different configurations:

```bash
# Test 1: Mock provider (default)
export PROVIDER=mock
pytest tests/test_api.py -v

# Test 2: Local provider with small model
export PROVIDER=local
export EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
export EMBEDDING_DIMENSION=384
pytest tests/test_api.py -v

# Test 3: Local provider with better model
export PROVIDER=local
export EMBEDDING_MODEL_ID=all-mpnet-base-v2
export EMBEDDING_DIMENSION=768
pytest tests/test_api.py -v
```

## Performance Testing

```python
# test_performance.py
import time
from mapper_copilot.providers.embeddings import SentenceTransformerEmbedder

embedder = SentenceTransformerEmbedder('all-MiniLM-L6-v2')

# Warm up
embedder.embed("warmup")

# Test single embeddings
texts = [f"Question {i}" for i in range(100)]

start = time.time()
for text in texts:
    embedder.embed(text)
single_time = time.time() - start

# Test batch embeddings
start = time.time()
embedder.batch_embed(texts)
batch_time = time.time() - start

print(f"100 embeddings:")
print(f"  Single: {single_time:.2f}s ({single_time/100*1000:.1f}ms each)")
print(f"  Batch:  {batch_time:.2f}s ({batch_time/100*1000:.1f}ms each)")
print(f"  Speedup: {single_time/batch_time:.1f}x")
```

## Troubleshooting

### Issue: "sentence-transformers not installed"

**Solution:**
```bash
pip install 'mapper-copilot[local-embeddings]'
```

### Issue: Tests are skipped

**Reason:** Tests are conditionally skipped if sentence-transformers isn't installed.

**Solution:** Install the package and re-run:
```bash
pip install sentence-transformers
pytest tests/test_embeddings.py::TestSentenceTransformerEmbedder -v
```

### Issue: Model download is slow

**First time only:** The model (120MB for all-MiniLM-L6-v2) needs to download from HuggingFace. Subsequent runs use cached model.

### Issue: Different Python interpreters

Make sure you're using the same Python that pytest uses:
```bash
which python
which pytest
# Should point to same environment
```

## Success Criteria

✅ All tests pass:
- 35 embedding tests (29 passed, 6 conditional)
- 8 API tests
- 11 suggester tests

✅ Manual test shows:
- Shape: (384,)
- Dtype: float32
- Norm: 1.0000

✅ API responds with:
- Valid mappings
- Confidence scores (0.0-1.0)
- Source candidates

✅ UI loads and generates mappings

## What to Test

| Test | Command | Expected Result |
|------|---------|----------------|
| Unit tests | `pytest tests/test_embeddings.py -v` | 35 tests pass |
| API tests | `pytest tests/test_api.py -v` | 8 tests pass |
| Manual check | `./test_embeddings_interactive.py` | Both providers work |
| API integration | `./test_local_api.sh` | Endpoints respond |
| UI | `./test_ui_with_local.sh` | Mappings generate |

## Next Steps

After testing:
1. Choose your provider in `.env`:
   ```bash
   PROVIDER=local
   EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
   ```

2. Run your application:
   ```bash
   # API
   uvicorn mapper_copilot.api:app --reload

   # UI
   streamlit run src/mapper_copilot/ui.py
   ```

3. For production, consider the better model:
   ```bash
   EMBEDDING_MODEL_ID=all-mpnet-base-v2
   EMBEDDING_DIMENSION=768
   ```
