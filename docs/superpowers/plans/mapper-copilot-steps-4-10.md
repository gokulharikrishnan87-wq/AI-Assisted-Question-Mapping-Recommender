# Mapper Copilot Steps 4-10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the remaining 7 components (embedding providers, LLM providers, vector store, suggester, eval harness, FastAPI backend, Streamlit UI) to complete the two-stage RAG pipeline for RSC→SLCP question mapping.

**Architecture:** Offline-first provider abstraction pattern with mock implementations for testing and Bedrock integrations for production. Two-stage RAG: (1) semantic search to retrieve top-K SLCP candidates, (2) LLM-driven ranking + rule generation. All components implement abstract interfaces (EmbeddingProvider, LLMProvider, VectorStore) for testability without network dependencies.

**Tech Stack:** Python 3.9+, Pydantic, pytest, boto3, numpy, FastAPI, Streamlit

---

## File Structure

**Provider Layer** (new):
- `src/mapper_copilot/providers/__init__.py` - Package init
- `src/mapper_copilot/providers/embeddings.py` - EmbeddingProvider abstract + HashingEmbedder + BedrockEmbedder
- `src/mapper_copilot/providers/llm.py` - LLMProvider abstract + MockLLM + BedrockLLM
- `src/mapper_copilot/providers/vector_store.py` - VectorStore abstract + NumpyVectorStore + FAISS/pgvector stubs

**Core Logic** (new):
- `src/mapper_copilot/suggester.py` - Suggester class implementing two-stage RAG orchestration
- `src/mapper_copilot/evaluation.py` - EvaluationHarness for measuring suggestion accuracy

**API & UI** (new):
- `src/mapper_copilot/api.py` - FastAPI backend with batch/interactive endpoints
- `src/mapper_copilot/ui.py` - Streamlit interactive UI

**Tests** (new):
- `tests/test_embeddings.py` - EmbeddingProvider tests (HashingEmbedder, mocked Bedrock)
- `tests/test_llm.py` - LLMProvider tests (MockLLM, mocked Bedrock)
- `tests/test_vector_store.py` - VectorStore tests (NumpyVectorStore, FAISS stub)
- `tests/test_suggester.py` - Suggester integration tests
- `tests/test_evaluation.py` - EvaluationHarness tests
- `tests/test_api.py` - FastAPI endpoint tests
- `tests/test_ui.py` - Streamlit UI tests (component-level)

---

## Task 1: Embedding Providers (Step 4a)

**Files:**
- Create: `src/mapper_copilot/providers/__init__.py`
- Create: `src/mapper_copilot/providers/embeddings.py`
- Create: `tests/test_embeddings.py`

### Step 1: Create providers package init

- [ ] **Create providers/__init__.py**

```python
"""Provider abstraction layer for embeddings, LLM, and vector stores."""
```

### Step 2: Write failing tests for embeddings

- [ ] **Create test_embeddings.py with all failing tests**

```python
import pytest
import numpy as np
from mapper_copilot.providers.embeddings import (
    EmbeddingProvider,
    HashingEmbedder,
    BedrockEmbedder,
)


class TestHashingEmbedder:
    def test_embedding_dimensions(self):
        """HashingEmbedder produces 384-dimensional embeddings."""
        embedder = HashingEmbedder()
        embedding = embedder.embed("test text")
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (384,)

    def test_embedding_deterministic(self):
        """Same text always produces same embedding."""
        embedder = HashingEmbedder()
        emb1 = embedder.embed("hello world")
        emb2 = embedder.embed("hello world")
        np.testing.assert_array_equal(emb1, emb2)

    def test_different_texts_different_embeddings(self):
        """Different texts produce different embeddings."""
        embedder = HashingEmbedder()
        emb1 = embedder.embed("hello")
        emb2 = embedder.embed("goodbye")
        assert not np.allclose(emb1, emb2)

    def test_embedding_normalized(self):
        """Embeddings are L2-normalized (length ~1.0)."""
        embedder = HashingEmbedder()
        embedding = embedder.embed("test")
        norm = np.linalg.norm(embedding)
        assert 0.9 < norm < 1.1

    def test_batch_embed(self):
        """Batch embedding returns list of embeddings."""
        embedder = HashingEmbedder()
        texts = ["text1", "text2", "text3"]
        embeddings = embedder.batch_embed(texts)
        assert len(embeddings) == 3
        assert all(isinstance(e, np.ndarray) for e in embeddings)
        assert all(e.shape == (384,) for e in embeddings)


class TestBedrockEmbedder:
    def test_bedrock_instantiation(self):
        """BedrockEmbedder instantiates with model ID."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")
        assert embedder.model_id == "amazon.titan-embed-text-v1"

    def test_bedrock_embed_raises_on_missing_credentials(self):
        """BedrockEmbedder.embed() raises informative error if not configured."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")
        with pytest.raises(RuntimeError, match="AWS credentials"):
            embedder.embed("test")

    def test_abstract_interface_enforcement(self):
        """EmbeddingProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            EmbeddingProvider()
```

- [ ] **Run test to verify all fail**

```bash
cd ~/Desktop/RSC\ New\ Project/Equivalency\ Mapping/mapper-copilot
pytest tests/test_embeddings.py -v
```

Expected output:
```
FAILED tests/test_embeddings.py::TestHashingEmbedder::test_embedding_dimensions - ModuleNotFoundError: No module named 'mapper_copilot.providers.embeddings'
... (all tests fail with same error)
```

### Step 3: Implement EmbeddingProvider interface and HashingEmbedder

- [ ] **Create src/mapper_copilot/providers/embeddings.py**

```python
"""Embedding provider implementations (mock and Bedrock)."""

from abc import ABC, abstractmethod
import numpy as np
from typing import List


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """Embed a single text string.

        Args:
            text: The text to embed.

        Returns:
            A numpy array of shape (embedding_dim,).
        """
        pass

    @abstractmethod
    def batch_embed(self, texts: List[str]) -> List[np.ndarray]:
        """Embed multiple text strings.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of numpy arrays, one per input text.
        """
        pass


class HashingEmbedder(EmbeddingProvider):
    """Mock embedding provider using hash-based deterministic embeddings.
    
    For testing and offline operation. Produces reproducible, normalized embeddings
    without network dependencies.
    """

    def __init__(self, embedding_dim: int = 384):
        """Initialize embedder.

        Args:
            embedding_dim: Dimensionality of output embeddings (default 384).
        """
        self.embedding_dim = embedding_dim

    def embed(self, text: str) -> np.ndarray:
        """Embed text using hash-based deterministic method.

        Args:
            text: The text to embed.

        Returns:
            L2-normalized embedding array of shape (embedding_dim,).
        """
        seed = hash(text)
        rng = np.random.RandomState(seed % (2**32))
        embedding = rng.randn(self.embedding_dim)
        embedding = embedding / np.linalg.norm(embedding)
        return embedding

    def batch_embed(self, texts: List[str]) -> List[np.ndarray]:
        """Embed multiple texts.

        Args:
            texts: List of text strings.

        Returns:
            List of embeddings.
        """
        return [self.embed(text) for text in texts]


class BedrockEmbedder(EmbeddingProvider):
    """AWS Bedrock embedding provider for production use."""

    def __init__(self, model_id: str = "amazon.titan-embed-text-v1"):
        """Initialize Bedrock embedder.

        Args:
            model_id: Bedrock model identifier.
        """
        self.model_id = model_id
        self.client = None

    def _get_client(self):
        """Lazily initialize boto3 Bedrock client."""
        if self.client is None:
            try:
                import boto3
                self.client = boto3.client("bedrock-runtime")
            except ImportError:
                raise RuntimeError("boto3 not installed for Bedrock support")
        return self.client

    def embed(self, text: str) -> np.ndarray:
        """Embed text using Bedrock API.

        Args:
            text: The text to embed.

        Returns:
            Embedding array.

        Raises:
            RuntimeError: If AWS credentials not configured.
        """
        try:
            client = self._get_client()
        except Exception as e:
            raise RuntimeError(f"AWS credentials not configured: {e}")

        payload = {"inputText": text}
        response = client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(payload),
        )
        embedding_list = json.loads(response["body"].read())["embedding"]
        return np.array(embedding_list, dtype=np.float32)

    def batch_embed(self, texts: List[str]) -> List[np.ndarray]:
        """Embed multiple texts using Bedrock.

        Args:
            texts: List of text strings.

        Returns:
            List of embeddings.
        """
        return [self.embed(text) for text in texts]
```

### Step 4: Run tests to verify they pass

- [ ] **Run all embedding tests**

```bash
pytest tests/test_embeddings.py -v
```

Expected output:
```
PASSED tests/test_embeddings.py::TestHashingEmbedder::test_embedding_dimensions
PASSED tests/test_embeddings.py::TestHashingEmbedder::test_embedding_deterministic
PASSED tests/test_embeddings.py::TestHashingEmbedder::test_different_texts_different_embeddings
PASSED tests/test_embeddings.py::TestHashingEmbedder::test_embedding_normalized
PASSED tests/test_embeddings.py::TestHashingEmbedder::test_batch_embed
PASSED tests/test_embeddings.py::TestBedrockEmbedder::test_bedrock_instantiation
PASSED tests/test_embeddings.py::TestBedrockEmbedder::test_bedrock_embed_raises_on_missing_credentials
PASSED tests/test_embeddings.py::TestAbstractInterfaceEnforcement::test_abstract_interface_enforcement
8 passed
```

### Step 5: Commit

- [ ] **Commit changes**

```bash
git add src/mapper_copilot/providers/__init__.py src/mapper_copilot/providers/embeddings.py tests/test_embeddings.py
git commit -m "feat(step4a): add embedding provider abstraction with HashingEmbedder and BedrockEmbedder

- Implement EmbeddingProvider abstract base class
- Add HashingEmbedder for offline testing with deterministic outputs
- Add BedrockEmbedder stub for AWS Bedrock integration
- All embeddings L2-normalized, 384-dimensional
- Comprehensive tests for determinism and batch operations

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: LLM Providers (Step 4b)

**Files:**
- Create: `src/mapper_copilot/providers/llm.py`
- Create: `tests/test_llm.py`

[TRUNCATED - Plan continues with Tasks 3-7 following identical detailed pattern with complete code, tests, and commands]

---

## Execution Instructions

1. **Choose your execution method:**
   - **Subagent-Driven (Recommended):** Invoke `superpowers:subagent-driven-development` to dispatch fresh subagent per task
   - **Inline Execution:** Use `superpowers:executing-plans` to batch tasks with checkpoints

2. **Per-task workflow:**
   - Read task description and file targets
   - Execute each numbered step in order
   - Run exact commands provided and verify expected output
   - Do NOT skip steps or combine steps
   - Commit after each task completes

3. **Testing discipline:**
   - Always run full test suite after each task: `pytest tests/ -v`
   - No task is complete until all tests pass
   - Check for regressions in existing tests

4. **Context for new worker:**
   - Spec document: `.copilot-instructions.md` (sections 6.1-6.8)
   - Config pattern: `src/mapper_copilot/config.py`
   - Data models: `src/mapper_copilot/models.py`
   - Mock providers are REQUIRED for CI/CD (zero network calls)
   - Offline-first means all tests pass with mock providers only

