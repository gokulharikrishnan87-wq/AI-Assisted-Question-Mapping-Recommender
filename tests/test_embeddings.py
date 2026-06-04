import io
from pathlib import Path
import subprocess
import sys

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

    def test_bedrock_embed_wraps_invoke_model_errors(self, monkeypatch):
        """BedrockEmbedder wraps invoke_model credential errors in RuntimeError."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")

        class FailingClient:
            def invoke_model(self, **kwargs):
                raise Exception("Unable to locate credentials")

        monkeypatch.setattr(embedder, "_get_client", lambda: FailingClient())

        with pytest.raises(RuntimeError, match="AWS credentials"):
            embedder.embed("test")

    def test_bedrock_embed_preserves_non_credential_errors(self, monkeypatch):
        """BedrockEmbedder surfaces non-credential Bedrock failures accurately."""
        embedder = BedrockEmbedder(model_id="amazon.titan-embed-text-v1")

        class FailingClient:
            def invoke_model(self, **kwargs):
                raise Exception("Model not found")

        monkeypatch.setattr(embedder, "_get_client", lambda: FailingClient())

        with pytest.raises(RuntimeError, match="Bedrock request failed"):
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

    def test_abstract_interface_enforcement(self):
        """EmbeddingProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            EmbeddingProvider()
