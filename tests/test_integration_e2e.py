from __future__ import annotations

from typing import Iterable

import pytest
from fastapi.testclient import TestClient

from mapper_copilot import api
from mapper_copilot.config import Settings
from mapper_copilot.core.suggester import Suggester
from mapper_copilot.evaluation import EvaluationHarness, EvaluationResult
from mapper_copilot.models import Mapping
from mapper_copilot.providers.embeddings import HashingEmbedder
from mapper_copilot.providers.llm import MockLLM
from mapper_copilot.providers.vector_store import NumpyVectorStore


@pytest.fixture
def realistic_pairs() -> list[dict[str, str]]:
    return [
        {
            "rsc": "The facility has a valid business license for legal operation.",
            "slcp": "Operating license/registration is available and up to date",
        },
        {
            "rsc": "Worker employment contracts are maintained and signed.",
            "slcp": "Worker contracts are maintained and signed",
        },
        {
            "rsc": "Emergency exits are clearly marked and unobstructed.",
            "slcp": "Emergency exits are clearly marked and unobstructed",
        },
        {
            "rsc": "Workers are paid accurately and on time.",
            "slcp": "Workers are paid accurately and on time",
        },
        {
            "rsc": "Workers can raise concerns through a grievance mechanism.",
            "slcp": "Workers have access to a grievance mechanism",
        },
        {
            "rsc": "Personal protective equipment is provided where hazards exist.",
            "slcp": "Required personal protective equipment is provided and used",
        },
    ]


@pytest.fixture
def extended_pairs(realistic_pairs: list[dict[str, str]]) -> list[dict[str, str]]:
    return realistic_pairs + [
        {
            "rsc": "Fire detection systems are tested regularly.",
            "slcp": "Fire alarms and detection systems are tested regularly",
        },
        {
            "rsc": "First aid kits are stocked and available in work areas.",
            "slcp": "First aid supplies are available in all required areas",
        },
        {
            "rsc": "Machine guards are installed on moving equipment.",
            "slcp": "Machine guarding is installed and maintained on hazardous equipment",
        },
        {
            "rsc": "Dormitory drinking water is safe and accessible.",
            "slcp": "Safe drinking water is available in dormitories and work areas",
        },
        {
            "rsc": "Overtime is voluntary and recorded accurately.",
            "slcp": "Overtime work is voluntary and time records are accurate",
        },
        {
            "rsc": "Employees receive training on emergency response procedures.",
            "slcp": "Workers are trained on emergency response procedures",
        },
    ]


def build_suggester(
    pairs: Iterable[dict[str, str]], embedding_dim: int = 384, top_k: int = 5
) -> tuple[Suggester, HashingEmbedder, NumpyVectorStore]:
    pair_list = list(pairs)
    embedder = HashingEmbedder(embedding_dim=embedding_dim)
    vector_store = NumpyVectorStore()
    vector_store.index(
        vectors=embedder.batch_embed([pair["rsc"] for pair in pair_list]),
        metadata=[{"question": pair["slcp"], "rsc_question": pair["rsc"]} for pair in pair_list],
    )
    suggester = Suggester(
        embedding_provider=embedder,
        llm_provider=MockLLM(),
        vector_store=vector_store,
        top_k=top_k,
    )
    return suggester, embedder, vector_store


def initialize_from_settings(
    settings: Settings, pairs: Iterable[dict[str, str]]
) -> tuple[Suggester, HashingEmbedder, NumpyVectorStore]:
    if settings.provider != "mock":
        raise ValueError("integration tests only support the mock provider")
    if settings.vector_store_type != "numpy":
        raise ValueError("integration tests only support the numpy vector store")
    return build_suggester(
        pairs,
        embedding_dim=settings.embedding_dimension,
        top_k=settings.retrieve_top_k,
    )


def test_e2e_rsc_to_slcp_mapping(realistic_pairs: list[dict[str, str]]):
    """Full end-to-end mapping from RSC question to SLCP suggestion."""
    suggester, _, _ = build_suggester(realistic_pairs, top_k=4)
    target = realistic_pairs[0]

    mapping = suggester.suggest(target["rsc"])

    assert isinstance(mapping, Mapping)
    assert mapping.rsc_question == target["rsc"]
    assert mapping.mapped_to == target["slcp"]
    assert 0.0 <= mapping.confidence <= 1.0
    assert mapping.rule
    assert len(mapping.source_candidates) == 4
    assert mapping.source_candidates[0] == target["slcp"]


def test_e2e_batch_mapping(realistic_pairs: list[dict[str, str]]):
    """Batch processing preserves order and produces valid results."""
    suggester, _, _ = build_suggester(realistic_pairs, top_k=3)
    questions = [pair["rsc"] for pair in realistic_pairs]

    results = suggester.suggest_batch(questions)

    assert len(results) == len(questions)
    assert [result.rsc_question for result in results] == questions
    assert [result.mapped_to for result in results] == [pair["slcp"] for pair in realistic_pairs]
    assert all(0.0 <= result.confidence <= 1.0 for result in results)
    assert all(result.source_candidates for result in results)


def test_e2e_with_different_embedding_dims(realistic_pairs: list[dict[str, str]]):
    """System works with non-default embedding dimensions."""
    suggester, embedder, _ = build_suggester(realistic_pairs, embedding_dim=256, top_k=2)

    mapping = suggester.suggest(realistic_pairs[1]["rsc"])

    assert embedder.embedding_dim == 256
    assert mapping.mapped_to == realistic_pairs[1]["slcp"]
    assert len(mapping.source_candidates) == 2


def test_e2e_top_k_retrieval(extended_pairs: list[dict[str, str]]):
    """Top-K candidates are returned in order of similarity."""
    _, embedder, vector_store = build_suggester(extended_pairs, top_k=5)
    query_text = extended_pairs[2]["rsc"]

    results = vector_store.query(embedder.embed(query_text), top_k=5)

    assert len(results) == 5
    assert results[0][0]["question"] == extended_pairs[2]["slcp"]
    assert results[0][1] == pytest.approx(1.0)
    scores = [score for _metadata, score in results]
    assert scores == sorted(scores, reverse=True)


def test_e2e_evaluation_accuracy(realistic_pairs: list[dict[str, str]]):
    """Evaluation harness correctly measures accuracy."""
    suggester, _, _ = build_suggester(realistic_pairs, top_k=3)
    harness = EvaluationHarness(suggester)
    test_cases = [
        {
            "rsc_question": realistic_pairs[0]["rsc"],
            "expected_slcp_question": realistic_pairs[0]["slcp"],
        },
        {
            "rsc_question": realistic_pairs[1]["rsc"],
            "expected_slcp_question": realistic_pairs[1]["slcp"],
        },
        {
            "rsc_question": realistic_pairs[2]["rsc"],
            "expected_slcp_question": realistic_pairs[2]["slcp"],
        },
        {
            "rsc_question": realistic_pairs[3]["rsc"],
            "expected_slcp_question": realistic_pairs[4]["slcp"],
        },
    ]

    result = harness.evaluate(test_cases)

    assert isinstance(result, EvaluationResult)
    assert result.total == 4
    assert result.correct == 3
    assert result.accuracy == pytest.approx(0.75)
    assert [detail["match"] for detail in result.details] == [True, True, True, False]


def test_e2e_api_with_real_suggester(monkeypatch: pytest.MonkeyPatch, realistic_pairs):
    """FastAPI endpoints work with real suggester instance."""
    suggester, _, _ = build_suggester(realistic_pairs, top_k=3)
    monkeypatch.setattr(api, "_build_suggester", lambda: suggester)
    api.suggester = None

    with TestClient(api.app) as client:
        single_response = client.post("/suggest", json={"rsc_question": realistic_pairs[0]["rsc"]})
        batch_response = client.post(
            "/suggest-batch",
            json={"rsc_questions": [pair["rsc"] for pair in realistic_pairs[:3]]},
        )

    assert single_response.status_code == 200
    single_payload = single_response.json()
    validated_single = api.SuggestResponse.model_validate(single_payload)
    assert validated_single.mapped_to == realistic_pairs[0]["slcp"]

    assert batch_response.status_code == 200
    batch_payload = batch_response.json()
    assert "results" in batch_payload
    validated_results = [
        api.SuggestResponse.model_validate(item) for item in batch_payload["results"]
    ]
    assert [item.rsc_question for item in validated_results] == [
        pair["rsc"] for pair in realistic_pairs[:3]
    ]
    assert [item.mapped_to for item in validated_results] == [
        pair["slcp"] for pair in realistic_pairs[:3]
    ]


def test_e2e_empty_vector_store_handling():
    """System gracefully handles empty vector store."""
    suggester = Suggester(HashingEmbedder(), MockLLM(), NumpyVectorStore())

    mapping = suggester.suggest("What is the capital of France?")

    assert mapping.rsc_question == "What is the capital of France?"
    assert mapping.mapped_to == ""
    assert mapping.confidence == 0.0
    assert mapping.rule == ""
    assert mapping.source_candidates == []


def test_e2e_full_system_initialization(realistic_pairs: list[dict[str, str]]):
    """Entire system initializes and operates correctly."""
    settings = Settings(
        provider="mock",
        vector_store_type="numpy",
        embedding_dimension=256,
        retrieve_top_k=4,
    )
    suggester, embedder, _ = initialize_from_settings(settings, realistic_pairs)

    mapping = suggester.suggest(realistic_pairs[5]["rsc"])

    assert settings.provider == "mock"
    assert settings.vector_store_type == "numpy"
    assert embedder.embedding_dim == settings.embedding_dimension
    assert mapping.mapped_to == realistic_pairs[5]["slcp"]
    assert len(mapping.source_candidates) == settings.retrieve_top_k
