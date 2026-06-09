import builtins
import io
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from mapper_copilot.providers.embeddings import (
    BedrockEmbedder,
    EmbeddingProvider,
    HashingEmbedder,
    SentenceTransformerEmbedder,
    create_embedding_provider,
    create_embedding_provider_from_settings,
)


def _has_sentence_transformers() -> bool:
    """Check if sentence-transformers is installed."""
    try:
        import sentence_transformers
        return True
    except ImportError:
        return False


class TestHashingEmbedder:
    def test_embedding_dimensions(self):
        """HashingEmbedder produces 384-dimensional embeddings."""
        embedder = HashingEmbedder()
        embedding = embedder.embed("test text")
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (384,)

    def test_embedding_dtype_is_float32(self):
        """HashingEmbedder returns float32 embeddings."""
        embedder = HashingEmbedder()
        embedding = embedder.embed("test text")
        assert embedding.dtype == np.float32

    def test_embedding_deterministic(self):
        """Same text always produces same embedding."""
        embedder = HashingEmbedder()
        emb1 = embedder.embed("hello world")
        emb2 = embedder.embed("hello world")
        np.testing.assert_array_equal(emb1, emb2)

    def test_embedding_deterministic_across_processes(self):
        """Same text produces the same embedding across Python processes."""
        repo_root = Path(__file__).resolve().parents[1]
        script = "\n".join(
            [
                "import json",
                "import os",
                "import sys",
                "sys.path.insert(0, os.path.abspath('src'))",
                "from mapper_copilot.providers.embeddings import HashingEmbedder",
                "embedding = HashingEmbedder().embed('hello world')",
                "print(json.dumps(embedding.tolist()))",
            ]
        )

        emb1 = subprocess.check_output(
            [sys.executable, "-c", script],
            cwd=repo_root,
            text=True,
        ).strip()
        emb2 = subprocess.check_output(
            [sys.executable, "-c", script],
            cwd=repo_root,
            text=True,
        ).strip()

        assert emb1 == emb2

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

    def test_embedding_dimension_must_be_positive(self):
        """HashingEmbedder rejects non-positive embedding dimensions."""
        with pytest.raises(ValueError, match="embedding_dim must be greater than 0"):
            HashingEmbedder(embedding_dim=0)


class TestBedrockEmbedder:
    def test_bedrock_instantiation(self):
        """BedrockEmbedder instantiates with model ID."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")
        assert embedder.model_id == "amazon.titan-embed-text-v1"

    def test_bedrock_embed_raises_on_missing_credentials(self, monkeypatch):
        """BedrockEmbedder.embed() raises informative error if AWS creds are missing."""

        class FailingClient:
            def invoke_model(self, **kwargs):
                raise NoCredentialsError()

        fake_boto3 = SimpleNamespace(client=lambda service_name: FailingClient())
        monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")

        with pytest.raises(RuntimeError, match="AWS credentials not configured"):
            embedder.embed("test")

    def test_bedrock_embed_raises_when_boto3_missing(self, monkeypatch):
        """BedrockEmbedder reports missing boto3 dependency clearly."""
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "boto3":
                raise ImportError("No module named 'boto3'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")

        with pytest.raises(RuntimeError, match="boto3 not installed"):
            embedder.embed("test")

    def test_bedrock_embed_wraps_client_auth_errors(self, monkeypatch):
        """BedrockEmbedder classifies AWS auth-related credential failures."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")

        class FailingClient:
            def invoke_model(self, **kwargs):
                raise Exception("ExpiredTokenException: token expired")

        monkeypatch.setattr(embedder, "_get_client", lambda: FailingClient())

        with pytest.raises(RuntimeError, match="AWS credentials not configured"):
            embedder.embed("test")

    def test_bedrock_embed_preserves_non_credential_errors(self, monkeypatch):
        """BedrockEmbedder surfaces non-auth Bedrock failures accurately."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")

        class FailingClient:
            def invoke_model(self, **kwargs):
                raise Exception("ValidationException: model not found")

        monkeypatch.setattr(embedder, "_get_client", lambda: FailingClient())

        with pytest.raises(RuntimeError, match="Bedrock response parsing failed"):
            embedder.embed("test")

    def test_bedrock_embed_sends_json_headers(self, monkeypatch):
        """BedrockEmbedder sends JSON headers required by Bedrock."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")
        captured = {}

        class SuccessfulClient:
            def invoke_model(self, **kwargs):
                captured.update(kwargs)
                return {"body": io.BytesIO(b'{"embedding": [0.1, 0.2]}')}

        monkeypatch.setattr(embedder, "_get_client", lambda: SuccessfulClient())

        embedding = embedder.embed("test")

        np.testing.assert_allclose(embedding, np.array([0.1, 0.2], dtype=np.float32))
        assert captured["contentType"] == "application/json"
        assert captured["accept"] == "application/json"

    def test_bedrock_batch_embed(self, monkeypatch):
        """BedrockEmbedder.batch_embed delegates to embed for each text."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")
        monkeypatch.setattr(
            embedder,
            "embed",
            lambda text: np.array([len(text)], dtype=np.float32),
        )

        embeddings = embedder.batch_embed(["a", "bb", "ccc"])

        assert len(embeddings) == 3
        np.testing.assert_array_equal(embeddings[0], np.array([1], dtype=np.float32))
        np.testing.assert_array_equal(embeddings[1], np.array([2], dtype=np.float32))
        np.testing.assert_array_equal(embeddings[2], np.array([3], dtype=np.float32))

    def test_bedrock_embed_wraps_response_parse_errors(self, monkeypatch):
        """BedrockEmbedder wraps malformed response payloads consistently."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")

        class SuccessfulClient:
            def invoke_model(self, **kwargs):
                return {"body": io.BytesIO(b"not-json")}

        monkeypatch.setattr(embedder, "_get_client", lambda: SuccessfulClient())

        with pytest.raises(RuntimeError, match="Bedrock response parsing failed"):
            embedder.embed("test")

    def test_bedrock_embed_raises_when_embedding_missing(self, monkeypatch):
        """BedrockEmbedder rejects responses without an embedding field."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")

        class SuccessfulClient:
            def invoke_model(self, **kwargs):
                return {"body": io.BytesIO(b'{"vector": [0.1, 0.2]}')}

        monkeypatch.setattr(embedder, "_get_client", lambda: SuccessfulClient())

        with pytest.raises(RuntimeError, match="Bedrock response parsing failed"):
            embedder.embed("test")

    def test_abstract_interface_enforcement(self):
        """EmbeddingProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            EmbeddingProvider()


class TestSentenceTransformerEmbedder:
    """Tests for SentenceTransformerEmbedder."""

    def test_instantiation(self):
        """SentenceTransformerEmbedder instantiates with model name."""
        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")
        assert embedder.model_name == "all-MiniLM-L6-v2"
        assert embedder._model is None

    def test_default_model(self):
        """SentenceTransformerEmbedder defaults to all-MiniLM-L6-v2."""
        embedder = SentenceTransformerEmbedder()
        assert embedder.model_name == "all-MiniLM-L6-v2"

    @pytest.mark.skipif(not _has_sentence_transformers(), reason="sentence-transformers not installed")
    def test_lazy_initialization(self):
        """Model is loaded lazily on first embed call."""
        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        assert embedder._model is None
        embedder.embed("test")
        assert embedder._model is not None

    @pytest.mark.skipif(not _has_sentence_transformers(), reason="sentence-transformers not installed")
    def test_embedding_shape_and_dtype(self):
        """Embeddings have correct shape and dtype."""
        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        embedding = embedder.embed("test text")
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (384,)
        assert embedding.dtype == np.float32

    @pytest.mark.skipif(not _has_sentence_transformers(), reason="sentence-transformers not installed")
    def test_embedding_normalized(self):
        """Embeddings are L2-normalized."""
        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        embedding = embedder.embed("test")
        norm = np.linalg.norm(embedding)
        assert 0.99 < norm < 1.01

    @pytest.mark.skipif(not _has_sentence_transformers(), reason="sentence-transformers not installed")
    def test_embedding_dimension_property(self):
        """embedding_dim property returns correct dimension."""
        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        assert embedder.embedding_dim == 384

    @pytest.mark.skipif(not _has_sentence_transformers(), reason="sentence-transformers not installed")
    def test_batch_embed(self):
        """Batch embedding returns list of embeddings."""
        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        texts = ["text1", "text2", "text3"]
        embeddings = embedder.batch_embed(texts)
        assert len(embeddings) == 3
        assert all(isinstance(e, np.ndarray) for e in embeddings)
        assert all(e.shape == (384,) for e in embeddings)
        assert all(e.dtype == np.float32 for e in embeddings)

    @pytest.mark.skipif(not _has_sentence_transformers(), reason="sentence-transformers not installed")
    def test_batch_normalized(self):
        """Batch embeddings are L2-normalized."""
        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        embeddings = embedder.batch_embed(["text1", "text2"])
        for emb in embeddings:
            norm = np.linalg.norm(emb)
            assert 0.99 < norm < 1.01

    def test_missing_dependency_error(self, monkeypatch):
        """Clear error when sentence-transformers not installed."""
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "sentence_transformers":
                raise ImportError("No module named 'sentence_transformers'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")

        with pytest.raises(RuntimeError, match="sentence-transformers not installed"):
            embedder.embed("test")


class TestEmbeddingProviderFactory:
    """Tests for embedding provider factory functions."""

    def test_create_mock_provider(self):
        """Factory creates HashingEmbedder for mock provider."""
        embedder = create_embedding_provider("mock", embedding_dim=256)
        assert isinstance(embedder, HashingEmbedder)
        assert embedder.embedding_dim == 256

    def test_create_bedrock_provider(self):
        """Factory creates BedrockEmbedder for bedrock provider."""
        embedder = create_embedding_provider("bedrock", model_id="test-model")
        assert isinstance(embedder, BedrockEmbedder)
        assert embedder.model_id == "test-model"

    def test_create_bedrock_provider_default_model(self):
        """Factory uses default Bedrock model if not specified."""
        embedder = create_embedding_provider("bedrock")
        assert isinstance(embedder, BedrockEmbedder)
        assert embedder.model_id == "amazon.titan-embed-text-v1"

    def test_create_local_provider(self):
        """Factory creates SentenceTransformerEmbedder for local provider."""
        embedder = create_embedding_provider("local", model_id="all-MiniLM-L6-v2")
        assert isinstance(embedder, SentenceTransformerEmbedder)
        assert embedder.model_name == "all-MiniLM-L6-v2"

    def test_create_local_provider_default_model(self):
        """Factory uses default local model if not specified."""
        embedder = create_embedding_provider("local")
        assert isinstance(embedder, SentenceTransformerEmbedder)
        assert embedder.model_name == "all-MiniLM-L6-v2"

    def test_invalid_provider_raises(self):
        """Factory raises ValueError for invalid provider."""
        with pytest.raises(ValueError, match="Invalid provider 'invalid'"):
            create_embedding_provider("invalid")

    def test_create_from_settings_mock(self, monkeypatch):
        """create_embedding_provider_from_settings uses settings values."""
        from mapper_copilot.config import Settings

        fake_settings = Settings(
            provider="mock",
            embedding_dimension=512,
        )
        monkeypatch.setattr("mapper_copilot.config.settings", fake_settings)

        embedder = create_embedding_provider_from_settings()
        assert isinstance(embedder, HashingEmbedder)
        assert embedder.embedding_dim == 512

    def test_create_from_settings_local(self, monkeypatch):
        """create_embedding_provider_from_settings creates local provider."""
        from mapper_copilot.config import Settings

        fake_settings = Settings(
            provider="local",
            embedding_model_id="all-mpnet-base-v2",
        )
        monkeypatch.setattr("mapper_copilot.config.settings", fake_settings)

        embedder = create_embedding_provider_from_settings()
        assert isinstance(embedder, SentenceTransformerEmbedder)
        assert embedder.model_name == "all-mpnet-base-v2"
