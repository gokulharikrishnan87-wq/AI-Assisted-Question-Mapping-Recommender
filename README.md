# Mapper Copilot — AI-Assisted RSC→SLCP Mapper Suggester

A Streamlit-based UI + FastAPI backend for suggesting SLCP→RSC question mappings using semantic search (embeddings) + LLM reasoning. Two-stage RAG pipeline designed to accelerate the manual mapper creation process.

## Features

- **Two-stage RAG:**
  1. **Retrieve** — semantic search (~800 SLCP questions → top-N candidates via embeddings)
  2. **Reason** — LLM ranks candidates and drafts mapping rule fields (compliant_answer, match_type)

- **Offline-first:** all providers pluggable with deterministic offline defaults (mock embeddings, mock LLM)
- **Bedrock-ready:** swap to AWS Bedrock (Titan Embeddings V2 + Claude) via env var
- **Eval harness:** batch evaluation against ground-truth mappings (Hit@k, Precision@k, MRR)
- **Minimal POC:** stripped-down for demo; draft rules only (compliant_answer, match_type, minimal qualifiers)

## Quick start

### 1. Install

```bash
cd mapper-copilot
python -m venv .venv
source .venv/bin/activate  # or: .venv\Scripts\activate on Windows
pip install -e .
```

### 2. Configure

Copy `.env.example` → `.env` and adjust:

```bash
cp .env.example .env
# Edit .env if needed (defaults use mock providers, no AWS required)
```

### 3. Run Streamlit UI

```bash
streamlit run ui/app.py
```

Then upload two Excel files:
- **RSC questions:** id, description, section (columns configurable)
- **SLCP questions:** key, question, section

Pick an RSC question → see ranked SLCP candidates + LLM pick + rationale + draft rule.

### 4. Run tests (offline)

```bash
pytest tests/ -v
```

All tests pass with `PROVIDER=mock` (no network, no AWS creds).

### 5. Switch to AWS Bedrock (when on corporate network)

Set in `.env`:
```
PROVIDER=bedrock
AWS_REGION=us-west-2
AWS_PROFILE=your-profile
```

Then run Streamlit or FastAPI as normal — same interfaces, real models.

## Project structure

```
mapper-copilot/
├── src/mapper_copilot/
│   ├── config.py              # Pydantic settings; env-driven provider selection
│   ├── models.py              # Pydantic types: RscQuestion, SlcpQuestion, MappingSuggestion
│   ├── providers/
│   │   ├── embeddings.py      # EmbeddingProvider interface + HashingEmbedder + BedrockEmbedder
│   │   └── llm.py             # LLMProvider interface + MockLLM + BedrockLLM (Claude)
│   ├── ingestion/
│   │   └── excel_loader.py    # Configurable column mapping, Excel→records
│   ├── index/
│   │   └── vector_store.py    # VectorStore interface + NumpyVectorStore + stubs
│   ├── core/
│   │   └── suggester.py       # Two-stage RAG: retrieve → reason
│   ├── eval/
│   │   └── harness.py         # Batch evaluation vs ground-truth (Hit@k, MRR, etc.)
│   └── api/
│       └── main.py            # FastAPI (secondary); /suggest, /evaluate, /health
├── ui/
│   └── app.py                 # Streamlit (primary); upload + demo + batch eval
├── tests/                     # pytest suite (offline, no Bedrock)
├── data/                      # Seed data (SLCP + RSC Excel files, mapper_data.json)
├── pyproject.toml             # Dependencies + project config
├── .env.example               # Configuration template
└── README.md                  # This file
```

## Architecture

```
RSC Excel + SLCP Excel
    ↓
Ingestion (configurable column map)
    ↓
EmbeddingProvider (mock | bedrock-titan)
    ↓
VectorStore (numpy cosine)
    ↓
Retrieve: top-N SLCP candidates
    ↓
LLMProvider (mock | bedrock-claude)
    ↓
Reason: LLM ranks + drafts rule
    ↓
MappingSuggestion (match, confidence, rationale, draft fields)
    ↓
Streamlit UI + Eval Harness
```

## Provider Abstraction

Every external dependency is pluggable:

| Component | Offline (default) | AWS Bedrock | Optional local |
|---|---|---|---|
| **Embeddings** | `HashingEmbedder` (token-hash) | `BedrockEmbedder` (Titan V2, 1024→512→256 dims) | `SentenceTransformerEmbedder` (all-MiniLM-L6) |
| **LLM** | `MockLLM` (lexical overlap) | `BedrockLLM` (Claude Sonnet) | N/A |
| **Vector Search** | `NumpyVectorStore` (cosine) | Same | Future: FAISS, pgvector |

**Switching is one env var:** `PROVIDER=mock|bedrock|local`

## Input format

### RSC Excel
Configurable columns (default: A=id, B=description, C=section). See `excel_loader.py` for column mapping.

### SLCP Excel
Configurable columns (default: A=key, B=question, C=section). Can be the SLCP data dictionary.

### Ground truth (for eval)
Existing RSC→SLCP mapping (e.g. `mapper_data.json`) with fields:
- `question_id` / `key` (RSC identifier)
- `slcp_key` (SLCP identifier)

## Evaluation metrics

The harness computes:
- **Hit@k** — % of correct mappings in top-k retrieved candidates
- **Precision@k** — # correct in top-k / k
- **Recall@k** — # correct in top-k / total correct
- **MRR** — mean reciprocal rank

## Next steps (post-POC)

- Add FAISS indexing for 10k+ questions
- Integrate pgvector for persistent vector DB
- Expand draft rules (qualifiers, aggregation rules, match_type variants)
- Add LLM confidence calibration
- Support user feedback loop → re-rank suggestions
- Package as reusable agent (agentic upgrade path)

## Contributing

1. Create `.env` from `.env.example`
2. Run `pytest tests/ -v` to validate offline
3. Add tests for new providers
4. Keep providers swappable (interface-based)

## License

MIT
