"""Vector store abstractions and provider implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

import numpy as np


Metadata = Dict[str, Any]
QueryResult = Tuple[Metadata, float]


class VectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    def index(self, vectors: List[np.ndarray], metadata: List[Metadata]) -> None:
        """Add vectors to the store with associated metadata."""
        pass

    @abstractmethod
    def query(self, query_vector: np.ndarray, top_k: int = 5) -> List[QueryResult]:
        """Return top-k nearest neighbors as metadata/score pairs."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored vectors."""
        pass


class NumpyVectorStore(VectorStore):
    """In-memory vector store backed by numpy arrays for offline testing."""

    def __init__(self) -> None:
        self._vectors: np.ndarray | None = None
        self._metadata: List[Metadata] = []

    def index(self, vectors: List[np.ndarray], metadata: List[Metadata]) -> None:
        """Add vectors and metadata to the in-memory store."""
        if len(vectors) != len(metadata):
            raise ValueError("vectors and metadata must have the same length")
        if not vectors:
            return

        normalized_vectors = np.vstack([self._normalize(vector) for vector in vectors])
        if self._vectors is None:
            self._vectors = normalized_vectors
        else:
            self._vectors = np.vstack([self._vectors, normalized_vectors])
        self._metadata.extend(dict(item) for item in metadata)

    def query(self, query_vector: np.ndarray, top_k: int = 5) -> List[QueryResult]:
        """Search for nearest neighbors using cosine similarity."""
        if self._vectors is None or not self._metadata or top_k <= 0:
            return []

        normalized_query = self._normalize(query_vector)
        scores = np.dot(self._vectors, normalized_query)
        limit = min(top_k, len(self._metadata))
        ranked_indices = np.argsort(scores)[::-1][:limit]
        return [(dict(self._metadata[index]), float(scores[index])) for index in ranked_indices]

    def clear(self) -> None:
        """Remove all indexed vectors and metadata."""
        self._vectors = None
        self._metadata = []

    @staticmethod
    def _normalize(vector: np.ndarray) -> np.ndarray:
        """Return an L2-normalized float32 vector."""
        array = np.asarray(vector, dtype=np.float32)
        norm = np.linalg.norm(array)
        if norm == 0:
            raise ValueError("vector norm must be greater than 0")
        return array / norm


class FAISSVectorStore(VectorStore):
    """Placeholder for a future FAISS-backed vector store implementation."""

    def index(self, vectors: List[np.ndarray], metadata: List[Metadata]) -> None:
        """Add vectors to a FAISS-backed store when implemented."""
        raise NotImplementedError("FAISSVectorStore is not implemented yet")

    def query(self, query_vector: np.ndarray, top_k: int = 5) -> List[QueryResult]:
        """Query a FAISS-backed store when implemented."""
        raise NotImplementedError("FAISSVectorStore is not implemented yet")

    def clear(self) -> None:
        """Clear a FAISS-backed store when implemented."""
        raise NotImplementedError("FAISSVectorStore is not implemented yet")


class PgVectorStore(VectorStore):
    """Placeholder for a future pgvector-backed PostgreSQL store implementation."""

    def index(self, vectors: List[np.ndarray], metadata: List[Metadata]) -> None:
        """Add vectors to a pgvector-backed store when implemented."""
        raise NotImplementedError("PgVectorStore is not implemented yet")

    def query(self, query_vector: np.ndarray, top_k: int = 5) -> List[QueryResult]:
        """Query a pgvector-backed store when implemented."""
        raise NotImplementedError("PgVectorStore is not implemented yet")

    def clear(self) -> None:
        """Clear a pgvector-backed store when implemented."""
        raise NotImplementedError("PgVectorStore is not implemented yet")
