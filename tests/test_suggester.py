from typing import Optional

import numpy as np
import pytest

from mapper_copilot.providers.embeddings import EmbeddingProvider
from mapper_copilot.providers.llm import LLMProvider
from mapper_copilot.providers.vector_store import NumpyVectorStore


class SpyEmbeddingProvider(EmbeddingProvider):
    def __init__(self, embeddings: dict[str, np.ndarray]):
        self.embeddings = {
            key: np.array(value, dtype=np.float32) for key, value in embeddings.items()
        }
        self.calls: list[str] = []

    def embed(self, text: str) -> np.ndarray:
        self.calls.append(text)
        return self.embeddings[text]

    def batch_embed(self, texts: list[str]) -> list[np.ndarray]:
        return [self.embed(text) for text in texts]


class SpyLLM(LLMProvider):
    def __init__(self, responses: Optional[dict[str, str]] = None, default_response: str = ""):
        self.responses = responses or {}
        self.default_response = default_response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        for question_snippet, response in self.responses.items():
            if question_snippet in prompt:
                return response
        return self.default_response

    def generate_batch(self, prompts: list[str]) -> list[str]:
        return [self.generate(prompt) for prompt in prompts]


@pytest.fixture
def candidate_questions() -> list[str]:
    return [
        "Operating license/registration is available and up to date",
        "Worker contracts are maintained and signed",
        "Emergency exits are clearly marked and unobstructed",
    ]


@pytest.fixture
def populated_store(candidate_questions: list[str]) -> NumpyVectorStore:
    store = NumpyVectorStore()
    store.index(
        vectors=[
            np.array([1.0, 0.0], dtype=np.float32),
            np.array([0.8, 0.2], dtype=np.float32),
            np.array([0.0, 1.0], dtype=np.float32),
        ],
        metadata=[{"question": question} for question in candidate_questions],
    )
    return store


@pytest.fixture
def embedding_provider() -> SpyEmbeddingProvider:
    return SpyEmbeddingProvider(
        {
            "The facility has a business license for legal operation.": np.array(
                [1.0, 0.0], dtype=np.float32
            ),
            "Emergency exits remain accessible during all shifts.": np.array(
                [0.0, 1.0], dtype=np.float32
            ),
        }
    )


def test_suggest_e2e_with_mock_providers(populated_store, embedding_provider, candidate_questions):
    from mapper_copilot.core.suggester import Suggester

    llm = SpyLLM(
        default_response=(
            f"Best match: {candidate_questions[0]}. Confidence: high. "
            "Map this RSC control to the SLCP operating license question when the facility confirms its legal registration is current."
        )
    )
    suggester = Suggester(embedding_provider, llm, populated_store, top_k=3)

    mapping = suggester.suggest("The facility has a business license for legal operation.")

    assert mapping.mapped_to == candidate_questions[0]
    assert mapping.rule == (
        "Map this RSC control to the SLCP operating license question when the facility confirms its legal registration is current."
    )
    assert mapping.source_candidates == candidate_questions


def test_suggest_returns_mapping_object(populated_store, embedding_provider):
    from mapper_copilot.core.suggester import Suggester
    from mapper_copilot.models import Mapping

    llm = SpyLLM(
        default_response="Best match: Operating license/registration is available and up to date. Confidence: medium. Align the licensing requirement directly."
    )
    suggester = Suggester(embedding_provider, llm, populated_store)

    mapping = suggester.suggest("The facility has a business license for legal operation.")

    assert isinstance(mapping, Mapping)
    assert mapping.rsc_question == "The facility has a business license for legal operation."


def test_suggest_batch_multiple_questions(populated_store, embedding_provider, candidate_questions):
    from mapper_copilot.core.suggester import Suggester

    llm = SpyLLM(
        responses={
            "business license": (
                f"Best match: {candidate_questions[0]}. Confidence: high. Match the legal license requirement directly."
            ),
            "Emergency exits": (
                f"Best match: {candidate_questions[2]}. Confidence: low. Match the exit accessibility requirement directly."
            ),
        }
    )
    suggester = Suggester(embedding_provider, llm, populated_store, top_k=2)

    mappings = suggester.suggest_batch(
        [
            "The facility has a business license for legal operation.",
            "Emergency exits remain accessible during all shifts.",
        ]
    )

    assert len(mappings) == 2
    assert [mapping.mapped_to for mapping in mappings] == [
        candidate_questions[0],
        candidate_questions[2],
    ]


def test_suggest_uses_embedding_and_llm(populated_store, embedding_provider):
    from mapper_copilot.core.suggester import Suggester

    llm = SpyLLM(
        default_response="Best match: Operating license/registration is available and up to date. Confidence: high. Match the license question directly."
    )
    suggester = Suggester(embedding_provider, llm, populated_store)

    suggester.suggest("The facility has a business license for legal operation.")

    assert embedding_provider.calls == ["The facility has a business license for legal operation."]
    assert len(llm.prompts) == 1
    assert "Candidate SLCP Questions:" in llm.prompts[0]


def test_suggest_includes_source_candidates(
    populated_store, embedding_provider, candidate_questions
):
    from mapper_copilot.core.suggester import Suggester

    llm = SpyLLM(
        default_response="Best match: Operating license/registration is available and up to date. Confidence: medium. Match the licensing requirement directly."
    )
    suggester = Suggester(embedding_provider, llm, populated_store, top_k=2)

    mapping = suggester.suggest("The facility has a business license for legal operation.")

    assert mapping.source_candidates == candidate_questions[:2]


@pytest.mark.parametrize(
    ("response", "expected_confidence"),
    [
        (
            "Best match: Operating license/registration is available and up to date. Confidence: high. Match the license question directly.",
            0.8,
        ),
        (
            "Best match: Operating license/registration is available and up to date. Confidence: medium. Match the license question directly.",
            0.5,
        ),
        (
            "Best match: Operating license/registration is available and up to date. Confidence: low. Match the license question directly.",
            0.3,
        ),
        (
            "Best match: Operating license/registration is available and up to date. Match the license question directly.",
            0.5,
        ),
    ],
)
def test_suggest_confidence_in_valid_range(
    populated_store, embedding_provider, response, expected_confidence
):
    from mapper_copilot.core.suggester import Suggester

    llm = SpyLLM(default_response=response)
    suggester = Suggester(embedding_provider, llm, populated_store)

    mapping = suggester.suggest("The facility has a business license for legal operation.")

    assert mapping.confidence == pytest.approx(expected_confidence)
    assert 0.0 <= mapping.confidence <= 1.0


def test_suggest_handles_empty_vector_store(embedding_provider):
    from mapper_copilot.core.suggester import Suggester

    llm = SpyLLM(default_response="This response should not be used.")
    suggester = Suggester(embedding_provider, llm, NumpyVectorStore())

    mapping = suggester.suggest("The facility has a business license for legal operation.")

    assert mapping.mapped_to == ""
    assert mapping.confidence == 0.0
    assert mapping.rule == ""
    assert mapping.source_candidates == []
    assert llm.prompts == []


def test_suggest_batch_preserves_order(populated_store, embedding_provider, candidate_questions):
    from mapper_copilot.core.suggester import Suggester

    llm = SpyLLM(
        responses={
            "business license": (
                f"Best match: {candidate_questions[0]}. Confidence: high. Match the legal license requirement directly."
            ),
            "Emergency exits": (
                f"Best match: {candidate_questions[2]}. Confidence: medium. Match the emergency exit requirement directly."
            ),
        }
    )
    suggester = Suggester(embedding_provider, llm, populated_store, top_k=3)
    questions = [
        "Emergency exits remain accessible during all shifts.",
        "The facility has a business license for legal operation.",
    ]

    mappings = suggester.suggest_batch(questions)

    assert [mapping.rsc_question for mapping in mappings] == questions
    assert [mapping.mapped_to for mapping in mappings] == [
        candidate_questions[2],
        candidate_questions[0],
    ]
