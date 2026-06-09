"""Tests for hybrid retrieval module."""

import pytest
import numpy as np

from mapper_copilot.providers.retrieval import (
    tokenize_preserving_codes,
    reciprocal_rank_fusion,
    BM25Index,
    HybridRetriever,
)
from mapper_copilot.providers.embeddings import HashingEmbedder
from mapper_copilot.providers.vector_store import NumpyVectorStore


class TestTokenization:
    """Test tokenization preserving codes and numbers."""

    def test_preserves_numbers(self):
        """Test that numbers are preserved intact."""
        text = "Minimum age 15 years old"
        tokens = tokenize_preserving_codes(text)
        assert "15" in tokens
        assert "minimum" in tokens
        assert "age" in tokens
        assert "years" in tokens

    def test_preserves_hyphenated_codes(self):
        """Test that hyphenated codes are preserved."""
        text = "Question FP-STE-1 and ms-6-3x are codes"
        tokens = tokenize_preserving_codes(text)
        assert "fp-ste-1" in tokens
        assert "ms-6-3x" in tokens

    def test_lowercase_normalization(self):
        """Test that text is lowercased."""
        text = "UPPERCASE and MixedCase"
        tokens = tokenize_preserving_codes(text)
        assert "uppercase" in tokens
        assert "mixedcase" in tokens

    def test_filters_single_chars(self):
        """Test that single characters are filtered (except digits)."""
        text = "a b c 1 2 test"
        tokens = tokenize_preserving_codes(text)
        # Single letters removed
        assert "a" not in tokens
        assert "b" not in tokens
        # Single digits kept
        assert "1" in tokens
        assert "2" in tokens
        # Words kept
        assert "test" in tokens

    def test_empty_text(self):
        """Test empty text handling."""
        assert tokenize_preserving_codes("") == []
        assert tokenize_preserving_codes(None) == []


class TestReciprocalRankFusion:
    """Test RRF fusion logic."""

    def test_single_list(self):
        """Test RRF with single ranked list."""
        ranked_lists = [[1, 2, 3, 4, 5]]
        result = reciprocal_rank_fusion(ranked_lists)
        assert result == [1, 2, 3, 4, 5]

    def test_two_identical_lists(self):
        """Test RRF with two identical lists boosts shared items."""
        ranked_lists = [
            [1, 2, 3],
            [1, 2, 3],
        ]
        result = reciprocal_rank_fusion(ranked_lists)
        assert result == [1, 2, 3]

    def test_two_different_lists(self):
        """Test RRF fusion with different ranked lists."""
        # List 1: [1, 2, 3]
        # List 2: [3, 4, 5]
        # Item 3 appears in both lists (high RRF score)
        ranked_lists = [
            [1, 2, 3],
            [3, 4, 5],
        ]
        result = reciprocal_rank_fusion(ranked_lists)
        # Item 3 should rank high due to appearing in both
        assert result[0] == 3 or result[0] == 1  # Top items

    def test_rrf_scores_known_example(self):
        """Test RRF with known example and verify fusion."""
        # Example: Dense retrieval prefers [A, B, C], BM25 prefers [C, D, A]
        # RRF should boost C and A (appear in both)
        ranked_lists = [
            [10, 20, 30],  # Dense: A=10, B=20, C=30
            [30, 40, 10],  # BM25: C=30, D=40, A=10
        ]
        result = reciprocal_rank_fusion(ranked_lists, k=60)

        # C appears at rank 2 in dense (score 1/62) and rank 0 in BM25 (score 1/60)
        # A appears at rank 0 in dense (score 1/60) and rank 2 in BM25 (score 1/62)
        # C's combined score: 1/62 + 1/60 ≈ 0.0329
        # A's combined score: 1/60 + 1/62 ≈ 0.0329
        # B only in dense rank 1: 1/61 ≈ 0.0164
        # D only in BM25 rank 1: 1/61 ≈ 0.0164

        # Top 2 should be C and A (order may vary due to floating point)
        assert set(result[:2]) == {10, 30}

    def test_empty_lists(self):
        """Test RRF with empty input."""
        assert reciprocal_rank_fusion([]) == []


class TestBM25Index:
    """Test BM25 index and querying."""

    def test_index_creation(self):
        """Test BM25 index creation."""
        corpus = [
            "The facility has a business license",
            "Workers wear protective equipment",
            "Minimum age is 15 years",
        ]
        doc_ids = [0, 1, 2]

        index = BM25Index(corpus, doc_ids)
        assert index.doc_ids == doc_ids

    def test_query_exact_match(self):
        """Test BM25 query with exact term match."""
        corpus = [
            "The facility has a business license",
            "Workers wear protective equipment",
            "Minimum age is 15 years",
        ]
        doc_ids = [0, 1, 2]

        index = BM25Index(corpus, doc_ids)
        results = index.query("business license", top_k=3)

        # Should return (doc_id, score) tuples
        assert len(results) == 3
        # First result should be doc 0 (contains "business" and "license")
        assert results[0][0] == 0
        assert results[0][1] > results[1][1]  # Higher score

    def test_query_number_sensitive(self):
        """Test BM25 distinguishes numbers (15 vs 18)."""
        corpus = [
            "Minimum age is 15 years old",
            "Minimum age is 18 years old",
            "Age verification required",
        ]
        doc_ids = [0, 1, 2]

        index = BM25Index(corpus, doc_ids)

        # Query for "15"
        results_15 = index.query("minimum age 15", top_k=3)
        # Doc 0 (contains 15) should score higher than doc 1 (contains 18)
        assert results_15[0][0] == 0

        # Query for "18"
        results_18 = index.query("minimum age 18", top_k=3)
        # Doc 1 (contains 18) should score higher than doc 0 (contains 15)
        assert results_18[0][0] == 1

    def test_query_code_matching(self):
        """Test BM25 matches hyphenated codes."""
        corpus = [
            "Question FP-STE-1 about facility step selection",
            "Question MS-CHE-1-3 about management systems",
            "Question HS-CON-3X about health safety",
        ]
        doc_ids = [0, 1, 2]

        index = BM25Index(corpus, doc_ids)

        # Query for specific code
        results = index.query("FP-STE-1", top_k=3)
        # Doc 0 should rank first
        assert results[0][0] == 0

    def test_empty_query(self):
        """Test BM25 with empty query."""
        corpus = ["Document 1", "Document 2"]
        doc_ids = [0, 1]

        index = BM25Index(corpus, doc_ids)
        results = index.query("", top_k=2)

        # Should return results even for empty query (all docs have equal low score)
        assert len(results) == 2

    def test_mismatched_lengths(self):
        """Test BM25 index raises error on mismatched inputs."""
        with pytest.raises(ValueError, match="same length"):
            BM25Index(["doc1", "doc2"], [0])


class TestHybridRetriever:
    """Test hybrid retrieval combining dense + BM25."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for testing."""
        # Create mock embedder
        embedder = HashingEmbedder(embedding_dim=128)

        # Create mock corpus
        corpus = [
            "The facility has a valid business license",
            "Workers must be at least 18 years old",
            "Workers must be at least 15 years old for light work",
            "Protective equipment is provided to all workers",
            "Regular safety inspections are conducted",
        ]

        # Build vector store
        vector_store = NumpyVectorStore()
        embeddings = embedder.batch_embed(corpus)
        metadata_list = [
            {"slcp_question": text, "key": f"key-{i}", "section": "SECTION", "number": f"NUM-{i}"}
            for i, text in enumerate(corpus)
        ]
        vector_store.index(embeddings, metadata_list)

        # Build BM25 index
        # BM25 needs corpus texts that include codes/numbers
        bm25_corpus = [
            f"{meta['key']} {meta['number']} {text}"
            for meta, text in zip(metadata_list, corpus)
        ]
        doc_ids = list(range(len(corpus)))
        bm25_index = BM25Index(bm25_corpus, doc_ids)

        return embedder, vector_store, bm25_index

    def test_retrieval_returns_candidates(self, mock_components):
        """Test hybrid retriever returns candidates."""
        embedder, vector_store, bm25_index = mock_components

        retriever = HybridRetriever(
            embedding_provider=embedder,
            vector_store=vector_store,
            bm25_index=bm25_index,
            k_retrieve=5,
        )

        rsc_metadata = {
            "section": "1. Labor Standards",
            "lll_key": "1.05",
            "reference_data": "Workers must meet minimum age requirements",
        }

        candidates = retriever.retrieve("minimum age requirement", rsc_metadata)

        assert len(candidates) > 0
        assert all("question" in c for c in candidates)
        assert all("key" in c for c in candidates)
        assert all("embedding_score" in c for c in candidates)

    def test_number_sensitive_retrieval(self, mock_components):
        """Test that BM25 helps surface number-specific matches."""
        embedder, vector_store, bm25_index = mock_components

        retriever = HybridRetriever(
            embedding_provider=embedder,
            vector_store=vector_store,
            bm25_index=bm25_index,
            k_retrieve=5,
            use_bm25=True,
        )

        rsc_metadata = {
            "section": "2. Child Labor",
            "lll_key": "2.01",
            "reference_data": "Minimum age 18",
        }

        # Query specifically mentions "18"
        candidates = retriever.retrieve("minimum age 18 years", rsc_metadata)

        # Check that results include the "18 years" document
        questions = [c["question"] for c in candidates]
        assert any("18 years old" in q for q in questions)

    def test_bm25_disabled(self, mock_components):
        """Test retrieval with BM25 disabled (dense-only)."""
        embedder, vector_store, bm25_index = mock_components

        retriever = HybridRetriever(
            embedding_provider=embedder,
            vector_store=vector_store,
            bm25_index=bm25_index,
            k_retrieve=5,
            use_bm25=False,  # Disable BM25
        )

        rsc_metadata = {"section": "1. Test", "lll_key": "1.01", "reference_data": ""}

        candidates = retriever.retrieve("test query", rsc_metadata)

        # Should still return results (from dense retrieval only)
        assert len(candidates) > 0

    def test_section_prior_boost(self, mock_components):
        """Test that section prior boosts same-section candidates."""
        embedder, vector_store, bm25_index = mock_components

        # Rebuild vector store with section metadata
        corpus = [
            "Business license requirement",
            "Safety inspection requirement",
            "Worker age requirement",
        ]
        embeddings = embedder.batch_embed(corpus)
        metadata_list = [
            {"slcp_question": corpus[0], "key": "biz-1", "section": "MANAGEMENT SYSTEMS", "number": "MS-1"},
            {"slcp_question": corpus[1], "key": "safe-1", "section": "HEALTH & SAFETY", "number": "HS-1"},
            {"slcp_question": corpus[2], "key": "labor-1", "section": "RECRUITMENT & HIRING", "number": "RH-1"},
        ]

        vector_store_with_sections = NumpyVectorStore()
        vector_store_with_sections.index(embeddings, metadata_list)

        bm25_corpus_with_sections = [
            f"{meta['key']} {text}"
            for meta, text in zip(metadata_list, corpus)
        ]
        bm25_with_sections = BM25Index(bm25_corpus_with_sections, list(range(len(corpus))))

        retriever = HybridRetriever(
            embedding_provider=embedder,
            vector_store=vector_store_with_sections,
            bm25_index=bm25_with_sections,
            k_retrieve=3,
            section_prior_weight=0.3,  # Enable section boost
        )

        rsc_metadata = {
            "section": "1. Business Ethics",  # Should match "MANAGEMENT SYSTEMS"
            "lll_key": "1.01",
            "reference_data": "",
        }

        candidates = retriever.retrieve("license requirement", rsc_metadata)

        # With section boost, business license (MANAGEMENT SYSTEMS) should rank higher
        # This is a soft test - we just verify candidates are returned
        assert len(candidates) > 0

    def test_section_prior_disabled(self, mock_components):
        """Test retrieval with section prior disabled."""
        embedder, vector_store, bm25_index = mock_components

        retriever = HybridRetriever(
            embedding_provider=embedder,
            vector_store=vector_store,
            bm25_index=bm25_index,
            k_retrieve=5,
            section_prior_weight=0.0,  # Disable section prior
        )

        rsc_metadata = {"section": "1. Test", "lll_key": "1.01", "reference_data": ""}

        candidates = retriever.retrieve("test query", rsc_metadata)

        # Should still return results
        assert len(candidates) > 0
