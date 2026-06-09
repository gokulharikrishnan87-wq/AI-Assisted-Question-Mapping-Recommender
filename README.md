# Mapper Copilot — AI-Assisted RSC→SLCP Question Mapping

A production-ready Streamlit application for automated mapping of RSC (Responsible Sourcing Checklist) questions to SLCP (Social & Labor Convergence Program) questions using **hybrid retrieval** (BM25 + dense embeddings) and **LLM-powered reranking**.

## 🎯 Overview

This tool accelerates the manual process of mapping ~288 RSC questions to a corpus of ~820 SLCP questions by:

1. **Hybrid Retrieval**: Combines BM25 (keyword/lexical matching) with dense semantic embeddings for robust candidate retrieval
2. **Smart Reranking**: Optional Claude-powered reranking for improved precision
3. **Batch Processing**: Map all RSC questions at once with intelligent caching
4. **Rich Metadata**: Display SLCP key, number, section, subsection, and category for each match
5. **Interactive UI**: Tabbed interface comparing semantic matches vs. Claude reranked results

## ✨ Features

### Core Capabilities

- **Hybrid Retrieval System**
  - BM25 for exact term matching (codes, keywords)
  - Dense embeddings for semantic similarity
  - Configurable fusion weights and section priors
  - Retrieves top-100 candidates for comprehensive coverage

- **Dual Reranking Options**
  - **Local Cross-Encoder**: Fast, offline reranking using sentence-transformers
  - **LLM Reranker**: Claude API for reasoning-based reranking with explanations

- **Enhanced UI**
  - Side-by-side comparison: Semantic match vs. Claude rerank tabs
  - Full SLCP metadata display (key, number, section, subsection, category)
  - Confidence scores and visual indicators
  - Export mappings to CSV
  - Filter by section and confidence threshold

- **Production Features**
  - Intelligent caching (avoids re-mapping on reload)
  - Batch processing with progress tracking
  - Section-aware similarity boosting
  - Configurable via environment variables

### Provider Support

| Component | Options | Notes |
|-----------|---------|-------|
| **Embeddings** | Local (sentence-transformers), AWS Bedrock (Titan V2) | Default: `all-MiniLM-L6-v2` (384-dim) |
| **Reranker** | Local (cross-encoder), LLM (Claude via API), Off | Optional, on-demand |
| **Vector Search** | Numpy (cosine similarity) | Fast for <10k questions |

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/gokulharikrishnan87-wq/AI-Assisted-Question-Mapping-Recommender.git
cd AI-Assisted-Question-Mapping-Recommender
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 2. Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

**Key settings:**

```bash
# Embedding provider
PROVIDER=local                          # local | bedrock
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2    # sentence-transformers model
EMBEDDING_DIMENSION=384

# Reranker (optional)
RERANKER=llm                            # off | local | llm
RERANKER_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=your-key-here         # Required for LLM reranker

# Hybrid retrieval settings
USE_BM25=true
K_RETRIEVE=100                          # Top-100 for reranking
SECTION_PRIOR_WEIGHT=0.1
```

### 3. Run the Application

#### Enhanced UI (Recommended)
```bash
streamlit run ui_enhanced.py
```

#### Basic UI
```bash
streamlit run src/mapper_copilot/ui.py
```

### 4. Usage

1. **First run**: Click "🚀 Start Mapping All Questions"
   - Maps all 288 RSC questions to SLCP corpus
   - Takes ~2-3 minutes with local embeddings
   - Results cached for instant reload

2. **Explore mappings**:
   - Browse all mappings with filters (section, confidence)
   - Click any mapping to see details
   - **Semantic match tab**: Shows hybrid retrieval results (BM25 + embeddings)
   - **Claude rerank tab**: Click to rerank with LLM (optional, uses API credits)

3. **Export**:
   - Click "📥 Export to CSV" for all mappings
   - Includes best match, alternatives, scores, and metadata

## 📁 Project Structure

```
AI-Assisted-Question-Mapping-Recommender/
├── src/mapper_copilot/
│   ├── config.py                    # Settings (env-driven)
│   ├── core/
│   │   └── suggester.py            # Main suggestion engine
│   ├── providers/
│   │   ├── embeddings.py           # Embedding providers (local, Bedrock)
│   │   ├── llm.py                  # LLM providers (mock, Bedrock)
│   │   ├── retrieval.py            # Hybrid retrieval (BM25 + dense)
│   │   ├── rerankers.py            # Reranking (cross-encoder, LLM)
│   │   └── vector_store.py         # Vector storage (numpy)
│   ├── ui.py                        # Basic Streamlit UI
│   ├── ui_simple_render.py          # Clean card rendering
│   └── api.py                       # FastAPI backend (optional)
├── ui_enhanced.py                   # Enhanced UI with tabs & metadata
├── data/
│   ├── RSC Questions.xlsx           # 288 RSC questions
│   └── slcp_data_dictionary.json    # 820 SLCP questions with metadata
├── tests/                           # Pytest suite
├── .env.example                     # Configuration template
└── README.md                        # This file
```

## 🔧 Architecture

### Hybrid Retrieval Pipeline

```
RSC Question
    ↓
┌─────────────────────────────────────┐
│  Hybrid Retriever                   │
│  ├─ BM25 Index (keyword matching)   │
│  └─ Dense Embeddings (semantic)     │
└─────────────────────────────────────┘
    ↓
Top-100 SLCP Candidates (merged & scored)
    ↓
┌─────────────────────────────────────┐
│  Optional Reranker                  │
│  ├─ Local: Cross-encoder            │
│  └─ LLM: Claude with reasoning      │
└─────────────────────────────────────┘
    ↓
Top-5 Final Matches + Metadata + Scores
```

### Key Components

**1. BM25 Index**
- Fast keyword/lexical search
- Excellent for matching codes (e.g., "MS-CHE-1-1")
- Handles exact term matching

**2. Dense Embeddings**
- Semantic similarity via sentence-transformers
- Captures conceptual relationships
- Works offline with local models

**3. Hybrid Fusion**
- Combines BM25 and embedding scores
- Section-aware boosting (+10% for matching sections)
- Retrieves top-100 for comprehensive coverage

**4. Reranking**
- **Cross-encoder**: Fast, accurate, offline
- **LLM**: Best quality, provides reasoning, uses API

## 📊 Data Format

### Input Files

**RSC Questions** (`RSC Questions.xlsx`):
- Columns: `LLL Key (unique)`, `LLL Description`, `Section`, `Reference Data`
- 288 questions across 10 sections

**SLCP Data** (`slcp_data_dictionary.json`):
```json
{
  "ms-6-1x": {
    "key": "ms-6-1x",
    "number": "MS-CHE-1-1",
    "section": "MANAGEMENT SYSTEMS",
    "subsection": "Check",
    "category": "Monitoring",
    "question": "Facility conducts regular internal reviews..."
  }
}
```

### Output Format

**CSV Export**:
- RSC question + metadata
- Top SLCP match (key, number, section, question)
- Confidence score
- Up to 5 alternative matches

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Test embeddings
pytest tests/test_embeddings.py -v

# Test retrieval
pytest tests/test_retrieval.py -v

# Test rerankers
pytest tests/test_rerankers.py -v
```

All tests pass offline with local providers (no API keys required).

## ⚙️ Configuration Options

### Embedding Providers

**Local (Default)**
```bash
PROVIDER=local
EMBEDDING_MODEL_ID=all-MiniLM-L6-v2
```

**AWS Bedrock**
```bash
PROVIDER=bedrock
AWS_REGION=us-west-2
AWS_PROFILE=your-profile
```

### Reranking Options

**Off** (fastest)
```bash
RERANKER=off
```

**Local Cross-Encoder** (fast, accurate)
```bash
RERANKER=local
CROSS_ENCODER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

**LLM (Claude)** (best quality, uses API)
```bash
RERANKER=llm
RERANKER_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-...
```

### Retrieval Tuning

```bash
# Hybrid retrieval
USE_BM25=true
K_RETRIEVE=100              # Top-N for reranking

# Section prior boost
SECTION_PRIOR_WEIGHT=0.1    # 10% boost for section match

# Embedding dimension
EMBEDDING_DIMENSION=384     # Model-specific
```

## 📈 Performance

With default settings (local embeddings, hybrid retrieval):
- **Initial mapping**: ~2-3 minutes for 288 RSC questions
- **Subsequent loads**: Instant (cached)
- **Per-question retrieval**: ~50-100ms
- **LLM reranking**: ~2-3s per question (on-demand)

## 🎓 Documentation

See the `docs/` folder for detailed guides:
- `QUICK_START.md` - Getting started guide
- `HYBRID_RETRIEVAL_QUICKSTART.md` - Retrieval system overview
- `RERANKER_IMPLEMENTATION.md` - Reranking options
- `TESTING_GUIDE.md` - Testing and validation

## 🛠️ Utilities

The project includes helper scripts in the root directory:
- `convert_slcp_excel.py` - Convert SLCP Excel to JSON
- `map_all_questions_enhanced.py` - Batch mapping script
- `test_hybrid_manual.py` - Manual retrieval testing
- `start_ui_enhanced.sh` - Launch enhanced UI

## 🔮 Roadmap

- [ ] FAISS indexing for 10k+ questions
- [ ] PostgreSQL + pgvector for production persistence
- [ ] User feedback loop for continuous improvement
- [ ] Multi-language support
- [ ] Export to multiple formats (Excel, JSON, CSV)
- [ ] API endpoints for integration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest tests/ -v`
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Embeddings by [sentence-transformers](https://www.sbert.net/)
- LLM reranking by [Anthropic Claude](https://www.anthropic.com/)
- BM25 implementation via [rank-bm25](https://github.com/dorianbrown/rank_bm25)

## 📧 Support

For questions or issues, please open a GitHub issue or contact the maintainers.

---

**Made with ❤️ for the social compliance and ethical sourcing community**
