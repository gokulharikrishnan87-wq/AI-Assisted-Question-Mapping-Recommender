import numpy as np
import pytest

from mapper_copilot.providers.vector_store import (
    FAISSVectorStore,
    NumpyVectorStore,
    PgVectorStore,
)


def normalize(values: list[float]) -> np.ndarray:
    vector = np.array(values, dtype=np.float32)
    return vector / np.linalg.norm(vector)


def test_vectorstore_index_and_query():
    store = NumpyVectorStore()
    store.index(
        vectors=[normalize([1.0, 0.0]), normalize([0.0, 1.0])],
        metadata=[{"id": "alpha"}, {"id": "beta"}],
    )

    results = store.query(normalize([1.0, 0.0]))

    assert len(results) == 2
    assert results[0][0] == {"id": "alpha"}
    assert results[0][1] == pytest.approx(1.0)


def test_vectorstore_query_top_k():
    store = NumpyVectorStore()
    store.index(
        vectors=[
            normalize([1.0, 0.0]),
            normalize([0.9, 0.1]),
            normalize([0.8, 0.2]),
        ],
        metadata=[{"id": "first"}, {"id": "second"}, {"id": "third"}],
    )

    results = store.query(normalize([1.0, 0.0]), top_k=2)

    assert [item[0]["id"] for item in results] == ["first", "second"]


def test_vectorstore_query_with_metadata():
    store = NumpyVectorStore()
    metadata = {"id": "candidate-1", "section": "Safety", "rank": 3}
    store.index(vectors=[normalize([1.0, 0.0])], metadata=[metadata])

    results = store.query(normalize([1.0, 0.0]))

    assert results == [(metadata, pytest.approx(1.0))]


def test_vectorstore_cosine_similarity():
    store = NumpyVectorStore()
    store.index(
        vectors=[
            normalize([1.0, 0.0]),
            normalize([1.0, 1.0]),
            normalize([0.0, 1.0]),
        ],
        metadata=[{"id": "x"}, {"id": "diag"}, {"id": "y"}],
    )

    results = store.query(normalize([1.0, 0.0]), top_k=3)
    scores = {item[0]["id"]: item[1] for item in results}

    assert scores["x"] == pytest.approx(1.0)
    assert scores["diag"] == pytest.approx(np.sqrt(2) / 2)
    assert scores["y"] == pytest.approx(0.0)


def test_vectorstore_query_empty_store():
    store = NumpyVectorStore()

    assert store.query(normalize([1.0, 0.0])) == []


def test_vectorstore_clear():
    store = NumpyVectorStore()
    store.index(vectors=[normalize([1.0, 0.0])], metadata=[{"id": "alpha"}])

    store.clear()

    assert store.query(normalize([1.0, 0.0])) == []


def test_vectorstore_batch_queries():
    store = NumpyVectorStore()
    store.index(
        vectors=[normalize([1.0, 0.0]), normalize([0.0, 1.0])],
        metadata=[{"id": "alpha"}, {"id": "beta"}],
    )

    first_results = store.query(normalize([1.0, 0.0]), top_k=1)
    second_results = store.query(normalize([0.0, 1.0]), top_k=1)

    assert first_results == [({"id": "alpha"}, pytest.approx(1.0))]
    assert second_results == [({"id": "beta"}, pytest.approx(1.0))]


def test_vectorstore_query_single_vector_multiple_matches():
    store = NumpyVectorStore()
    store.index(
        vectors=[
            normalize([1.0, 0.0]),
            normalize([0.8, 0.2]),
            normalize([0.6, 0.4]),
        ],
        metadata=[{"id": "first"}, {"id": "second"}, {"id": "third"}],
    )

    results = store.query(normalize([1.0, 0.0]), top_k=10)

    assert [item[0]["id"] for item in results] == ["first", "second", "third"]


def test_faiss_not_implemented():
    store = FAISSVectorStore()

    with pytest.raises(NotImplementedError):
        store.index([normalize([1.0, 0.0])], [{"id": "alpha"}])


def test_pgvector_not_implemented():
    store = PgVectorStore()

    with pytest.raises(NotImplementedError):
        store.query(normalize([1.0, 0.0]))
