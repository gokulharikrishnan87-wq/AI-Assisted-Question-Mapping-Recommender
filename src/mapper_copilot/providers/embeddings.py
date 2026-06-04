"""Embedding provider implementations (mock and Bedrock)."""

from abc import ABC, abstractmethod
import hashlib
import json
from typing import List

import numpy as np
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    NoRegionError,
    PartialCredentialsError,
)


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
        if embedding_dim <= 0:
            raise ValueError("embedding_dim must be greater than 0")
        self.embedding_dim = embedding_dim

    def embed(self, text: str) -> np.ndarray:
        """Embed text using hash-based deterministic method.

        Args:
            text: The text to embed.

        Returns:
            L2-normalized embedding array of shape (embedding_dim,).
        """
        seed = np.frombuffer(hashlib.sha256(text.encode("utf-8")).digest(), dtype=np.uint32)
        rng = np.random.default_rng(seed)
        embedding = rng.standard_normal(self.embedding_dim).astype(np.float32)
        embedding /= np.linalg.norm(embedding)
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
            payload = {"inputText": text}
            response = client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json",
            )
        except RuntimeError:
            raise
        except (NoCredentialsError, PartialCredentialsError, NoRegionError) as e:
            raise RuntimeError(f"AWS credentials not configured: {e}") from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            auth_error_codes = {
                "AccessDeniedException",
                "AccessDenied",
                "ExpiredToken",
                "ExpiredTokenException",
                "IncompleteSignature",
                "IncompleteSignatureException",
                "InvalidClientTokenId",
                "InvalidSignatureException",
                "MissingAuthenticationTokenException",
                "UnrecognizedClientException",
            }
            if error_code in auth_error_codes:
                raise RuntimeError(f"AWS credentials not configured: {e}") from e
            raise RuntimeError(f"Bedrock request failed: {e}") from e
        except BotoCoreError as e:
            raise RuntimeError(f"Bedrock request failed: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Bedrock request failed: {e}") from e

        try:
            response_body = response["body"].read()
            embedding_list = json.loads(response_body)["embedding"]
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            raise RuntimeError(f"Bedrock response parsing failed: {e}") from e

        return np.array(embedding_list, dtype=np.float32)

    def batch_embed(self, texts: List[str]) -> List[np.ndarray]:
        """Embed multiple texts using Bedrock.

        Args:
            texts: List of text strings.

        Returns:
            List of embeddings.
        """
        return [self.embed(text) for text in texts]
