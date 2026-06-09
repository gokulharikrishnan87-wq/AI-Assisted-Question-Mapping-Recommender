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


# ============================================================================
# Hybrid Retrieval Integration Tests
# ============================================================================


class TestHybridRetrieval:
    """Test suggester with hybrid retrieval (dense + BM25 + reranker)."""

    @pytest.fixture
    def slcp_corpus(self):
        """SLCP test corpus with metadata."""
        return [
            {
                "key": "ms-che-1",
                "number": "MS-CHE-1",
                "section": "MANAGEMENT SYSTEMS",
                "subsection": "Chemical Management",
                "question": "Does the facility have a chemical inventory list?",
            },
            {
                "key": "hs-con-18",
                "number": "HS-CON-18",
                "section": "HEALTH & SAFETY",
                "subsection": "Working Conditions",
                "question": "Are workers at least 18 years old?",
            },
            {
                "key": "hs-con-15",
                "number": "HS-CON-15",
                "section": "HEALTH & SAFETY",
                "subsection": "Working Conditions",
                "question": "Are workers at least 15 years old for light work?",
            },
            {
                "key": "fp-ste-1",
                "number": "FP-STE-1",
                "section": "FACILITY PROFILE",
                "subsection": "General",
                "question": "Does the facility have a valid business license?",
            },
        ]

    @pytest.fixture
    def hybrid_components(self, slcp_corpus):
        """Build hybrid retrieval components."""
        from mapper_copilot.providers.embeddings import HashingEmbedder
        from mapper_copilot.providers.vector_store import NumpyVectorStore
        from mapper_copilot.providers.retrieval import BM25Index, HybridRetriever

        embedder = HashingEmbedder(embedding_dim=128)

        # Build vector store
        slcp_texts = [item["question"] for item in slcp_corpus]
        embeddings = embedder.batch_embed(slcp_texts)
        metadata_list = [
            {
                "slcp_question": item["question"],
                "key": item["key"],
                "number": item["number"],
                "section": item["section"],
            }
            for item in slcp_corpus
        ]
        vector_store = NumpyVectorStore()
        vector_store.index(embeddings, metadata_list)

        # Build BM25 index
        bm25_corpus = [
            f"{item['key']} {item['number']} {item['question']}"
            for item in slcp_corpus
        ]
        doc_ids = list(range(len(slcp_corpus)))
        bm25_index = BM25Index(bm25_corpus, doc_ids)

        # Build retriever
        retriever = HybridRetriever(
            embedding_provider=embedder,
            vector_store=vector_store,
            bm25_index=bm25_index,
            k_retrieve=4,
            use_bm25=True,
            section_prior_weight=0.1,
        )

        return embedder, retriever

    def test_suggester_with_hybrid_retrieval(self, hybrid_components, slcp_corpus):
        """Test suggester with hybrid retrieval (no reranker)."""
        from mapper_copilot.core.suggester import Suggester

        embedder, retriever = hybrid_components
        llm = SpyLLM(
            default_response=f"Best match: {slcp_corpus[3]['question']}. Confidence: high. Match the business license requirement."
        )

        suggester = Suggester(
            embedding_provider=embedder,
            llm_provider=llm,
            retriever=retriever,
            top_k=3,
        )

        # Call with RSC metadata
        rsc_metadata = {
            "section": "1. Business Ethics",
            "lll_key": "1.01",
            "reference_data": "Facility must have valid operating permits",
        }
        mapping = suggester.suggest("Does the facility have a business license?", rsc_metadata)

        # Verify results
        assert mapping.mapped_to == slcp_corpus[3]["question"]
        assert len(mapping.source_candidates) <= 3
        assert mapping.confidence == 0.8  # "high" -> 0.8

    def test_suggester_with_hybrid_and_mock_reranker(self, hybrid_components, slcp_corpus):
        """Test suggester with hybrid retrieval + mock reranker."""
        from mapper_copilot.core.suggester import Suggester

        embedder, retriever = hybrid_components
        llm = SpyLLM(
            default_response=f"Best match: {slcp_corpus[1]['question']}. Confidence: medium. Match age requirement."
        )

        # Mock reranker that just reverses order
        class MockReranker:
            def rerank(self, rsc_question, candidates, top_k=5):
                return candidates[:top_k][::-1]  # Reverse order

        reranker = MockReranker()

        suggester = Suggester(
            embedding_provider=embedder,
            llm_provider=llm,
            retriever=retriever,
            reranker=reranker,
            top_k=2,
        )

        rsc_metadata = {
            "section": "2. Labor Standards",
            "lll_key": "2.01",
            "reference_data": "Minimum age 18",
        }
        mapping = suggester.suggest("Are workers at least 18 years old?", rsc_metadata)

        # Verify reranker was used (reversed order)
        assert len(mapping.source_candidates) == 2
        assert mapping.confidence == 0.5  # "medium" -> 0.5

    def test_suggester_hybrid_backward_compatibility(self, slcp_corpus):
        """Test that suggester still works without metadata (backward compatibility)."""
        from mapper_copilot.core.suggester import Suggester
        from mapper_copilot.providers.embeddings import HashingEmbedder
        from mapper_copilot.providers.vector_store import NumpyVectorStore
        from mapper_copilot.providers.retrieval import BM25Index, HybridRetriever

        embedder = HashingEmbedder(embedding_dim=128)

        # Build minimal retriever
        slcp_texts = [item["question"] for item in slcp_corpus]
        embeddings = embedder.batch_embed(slcp_texts)
        metadata_list = [
            {"slcp_question": item["question"], "key": item["key"]}
            for item in slcp_corpus
        ]
        vector_store = NumpyVectorStore()
        vector_store.index(embeddings, metadata_list)

        bm25_corpus = [item["question"] for item in slcp_corpus]
        bm25_index = BM25Index(bm25_corpus, list(range(len(slcp_corpus))))

        retriever = HybridRetriever(
            embedding_provider=embedder,
            vector_store=vector_store,
            bm25_index=bm25_index,
            k_retrieve=4,
            use_bm25=True,
        )

        llm = SpyLLM(default_response="Best match: chemical inventory. Confidence: low.")

        suggester = Suggester(
            embedding_provider=embedder,
            llm_provider=llm,
            retriever=retriever,
            top_k=2,
        )

        # Call WITHOUT metadata (should still work)
        mapping = suggester.suggest("Does the facility track chemicals?")

        assert len(mapping.source_candidates) <= 2
        assert mapping.confidence == 0.3  # "low" -> 0.3
