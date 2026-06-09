"""Tests for reranker provider implementations."""

import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from mapper_copilot.providers.rerankers import (
    LLMReranker,
    LocalCrossEncoderReranker,
    Reranker,
    create_reranker,
    create_reranker_from_settings,
)


class TestRerankerAbstraction:
    """Tests for Reranker abstract base class."""

    def test_abstract_interface_enforcement(self):
        """Reranker cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Reranker()


class TestLLMReranker:
    """Tests for LLMReranker implementation."""

    def test_instantiation_with_defaults(self):
        """LLMReranker instantiates with default model."""
        reranker = LLMReranker(api_key="test-key")
        assert reranker.model_id == "claude-sonnet-4-6"
        assert reranker._api_key == "test-key"
        assert reranker._client is None

    def test_instantiation_with_custom_model(self):
        """LLMReranker accepts custom model ID."""
        reranker = LLMReranker(model_id="claude-opus-4-8", api_key="test-key")
        assert reranker.model_id == "claude-opus-4-8"

    def test_lazy_client_initialization(self, monkeypatch):
        """Anthropic client is initialized lazily."""
        mock_anthropic_class = Mock()
        mock_anthropic_instance = Mock()
        mock_anthropic_class.return_value = mock_anthropic_instance

        # Mock the anthropic module
        mock_anthropic_module = SimpleNamespace(Anthropic=mock_anthropic_class)
        monkeypatch.setitem(sys.modules, "anthropic", mock_anthropic_module)

        reranker = LLMReranker(api_key="test-key")
        assert reranker._client is None

        # Trigger lazy initialization
        client = reranker._get_client()
        assert reranker._client is not None
        assert client is mock_anthropic_instance
        mock_anthropic_class.assert_called_once_with(api_key="test-key")

    def test_rerank_with_valid_json_response(self, monkeypatch):
        """LLMReranker parses well-formed JSON response correctly."""
        # Mock Anthropic client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [
            SimpleNamespace(
                text=json.dumps(
                    [
                        {
                            "slcp_key": "hs-con-3x",
                            "score": 0.95,
                            "reason": "Both questions address protective equipment requirements.",
                        },
                        {
                            "slcp_key": "hs-con-5x",
                            "score": 0.80,
                            "reason": "Related to safety gear provisions.",
                        },
                    ]
                )
            )
        ]
        mock_client.messages.create.return_value = mock_response

        reranker = LLMReranker(api_key="test-key")
        monkeypatch.setattr(reranker, "_get_client", lambda: mock_client)

        # Candidate list
        candidates = [
            {
                "key": "hs-con-3x",
                "number": "HS-CON-3",
                "section": "Health & Safety",
                "question": "Are workers provided with protective equipment?",
                "embedding_score": 0.75,
            },
            {
                "key": "hs-con-5x",
                "number": "HS-CON-5",
                "section": "Health & Safety",
                "question": "Is safety gear maintained regularly?",
                "embedding_score": 0.70,
            },
        ]

        result = reranker.rerank("Do employees wear PPE?", candidates, top_k=2)

        assert len(result) == 2
        assert result[0]["llm_rank"] == 1
        assert result[0]["llm_score"] == 0.95
        assert result[0]["key"] == "hs-con-3x"
        assert "protective equipment" in result[0]["reason"]
        assert result[1]["llm_rank"] == 2
        assert result[1]["llm_score"] == 0.80

    def test_rerank_strips_markdown_fences(self, monkeypatch):
        """LLMReranker strips markdown code fences before parsing."""
        mock_client = Mock()
        mock_response = Mock()
        # Response with markdown fences
        mock_response.content = [
            SimpleNamespace(
                text="```json\n"
                + json.dumps([{"slcp_key": "hs-con-3x", "score": 0.9, "reason": "Match"}])
                + "\n```"
            )
        ]
        mock_client.messages.create.return_value = mock_response

        reranker = LLMReranker(api_key="test-key")
        monkeypatch.setattr(reranker, "_get_client", lambda: mock_client)

        candidates = [
            {
                "key": "hs-con-3x",
                "question": "Test question",
                "section": "Test",
                "embedding_score": 0.5,
            }
        ]

        result = reranker.rerank("Test RSC question", candidates, top_k=1)

        assert len(result) == 1
        assert result[0]["llm_score"] == 0.9

    def test_rerank_falls_back_on_malformed_json(self, monkeypatch):
        """LLMReranker falls back to embedding order on malformed JSON."""
        mock_client = Mock()
        mock_response = Mock()
        # Malformed JSON
        mock_response.content = [SimpleNamespace(text="This is not JSON at all!")]
        mock_client.messages.create.return_value = mock_response

        reranker = LLMReranker(api_key="test-key")
        monkeypatch.setattr(reranker, "_get_client", lambda: mock_client)

        candidates = [
            {
                "key": "hs-con-3x",
                "question": "Test question 1",
                "section": "Test",
                "embedding_score": 0.8,
            },
            {
                "key": "hs-con-5x",
                "question": "Test question 2",
                "section": "Test",
                "embedding_score": 0.7,
            },
        ]

        result = reranker.rerank("Test RSC question", candidates, top_k=2)

        # Should fall back to embedding order
        assert len(result) == 2
        assert result[0]["llm_rank"] == 1
        assert result[0]["key"] == "hs-con-3x"
        assert result[0]["reason"] == "Fallback: using embedding similarity"
        assert result[0]["llm_score"] == 0.8

    def test_rerank_falls_back_on_api_error(self, monkeypatch):
        """LLMReranker falls back to embedding order on API errors."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API error")

        reranker = LLMReranker(api_key="test-key")
        monkeypatch.setattr(reranker, "_get_client", lambda: mock_client)

        candidates = [
            {
                "key": "hs-con-3x",
                "question": "Test question",
                "section": "Test",
                "embedding_score": 0.75,
            }
        ]

        result = reranker.rerank("Test RSC question", candidates, top_k=1)

        # Should fall back gracefully
        assert len(result) == 1
        assert result[0]["reason"] == "Fallback: using embedding similarity"

    def test_rerank_with_empty_candidates(self, monkeypatch):
        """LLMReranker handles empty candidate list."""
        reranker = LLMReranker(api_key="test-key")
        result = reranker.rerank("Test question", [], top_k=5)
        assert result == []

    def test_rerank_sends_correct_parameters(self, monkeypatch):
        """LLMReranker sends correct API parameters."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [
            SimpleNamespace(text=json.dumps([{"slcp_key": "test", "score": 0.9, "reason": "Test"}]))
        ]
        mock_client.messages.create.return_value = mock_response

        reranker = LLMReranker(model_id="claude-opus-4-8", api_key="test-key")
        monkeypatch.setattr(reranker, "_get_client", lambda: mock_client)

        candidates = [
            {"key": "test", "question": "Q", "section": "S", "embedding_score": 0.5}
        ]

        reranker.rerank("RSC question", candidates, top_k=5)

        # Verify API call parameters
        call_args = mock_client.messages.create.call_args
        assert call_args.kwargs["model"] == "claude-opus-4-8"
        assert call_args.kwargs["max_tokens"] == 1024
        assert call_args.kwargs["temperature"] == 0
        assert len(call_args.kwargs["messages"]) == 1
        assert call_args.kwargs["messages"][0]["role"] == "user"

    def test_missing_anthropic_package(self, monkeypatch):
        """LLMReranker reports missing anthropic package clearly."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        reranker = LLMReranker(api_key="test-key")

        with pytest.raises(RuntimeError, match="anthropic package not installed"):
            reranker._get_client()


class TestLocalCrossEncoderReranker:
    """Tests for LocalCrossEncoderReranker stub."""

    def test_instantiation(self):
        """LocalCrossEncoderReranker instantiates with model name."""
        reranker = LocalCrossEncoderReranker(model_name="test-model")
        assert reranker.model_name == "test-model"

    def test_default_model(self):
        """LocalCrossEncoderReranker uses default model."""
        reranker = LocalCrossEncoderReranker()
        assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def test_rerank_raises_not_implemented(self):
        """LocalCrossEncoderReranker.rerank raises NotImplementedError."""
        reranker = LocalCrossEncoderReranker()
        candidates = [{"key": "test", "question": "Q", "section": "S"}]

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            reranker.rerank("Test question", candidates, top_k=5)


class TestRerankerFactory:
    """Tests for reranker factory functions."""

    def test_create_reranker_none(self):
        """Factory returns None when reranker_type is 'none'."""
        reranker = create_reranker(reranker_type="none")
        assert reranker is None

    def test_create_reranker_empty_string(self):
        """Factory returns None for empty reranker_type."""
        reranker = create_reranker(reranker_type="")
        assert reranker is None

    def test_create_reranker_llm_without_api_key(self):
        """Factory returns None when reranker_type is 'llm' but no API key."""
        reranker = create_reranker(reranker_type="llm", api_key=None)
        assert reranker is None

    def test_create_reranker_llm_with_api_key(self):
        """Factory returns LLMReranker when reranker_type is 'llm' and API key present."""
        reranker = create_reranker(reranker_type="llm", api_key="test-key")
        assert isinstance(reranker, LLMReranker)
        assert reranker.model_id == "claude-sonnet-4-6"
        assert reranker._api_key == "test-key"

    def test_create_reranker_llm_with_custom_model(self):
        """Factory uses custom model ID for LLM reranker."""
        reranker = create_reranker(
            reranker_type="llm", model_id="claude-opus-4-8", api_key="test-key"
        )
        assert isinstance(reranker, LLMReranker)
        assert reranker.model_id == "claude-opus-4-8"

    def test_create_reranker_local(self):
        """Factory creates LocalCrossEncoderReranker for 'local' type."""
        reranker = create_reranker(reranker_type="local")
        assert isinstance(reranker, LocalCrossEncoderReranker)
        assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def test_create_reranker_local_with_custom_model(self):
        """Factory uses custom model for local reranker."""
        reranker = create_reranker(reranker_type="local", model_id="custom-model")
        assert isinstance(reranker, LocalCrossEncoderReranker)
        assert reranker.model_name == "custom-model"

    def test_create_reranker_invalid_type(self):
        """Factory raises ValueError for invalid reranker type."""
        with pytest.raises(ValueError, match="Invalid reranker type 'invalid'"):
            create_reranker(reranker_type="invalid")

    def test_create_reranker_from_settings_none(self, monkeypatch):
        """create_reranker_from_settings returns None when RERANKER=none."""
        from mapper_copilot.config import Settings

        fake_settings = Settings(
            reranker="none",
        )
        monkeypatch.setattr("mapper_copilot.config.settings", fake_settings)

        reranker = create_reranker_from_settings()
        assert reranker is None

    def test_create_reranker_from_settings_llm_without_key(self, monkeypatch):
        """create_reranker_from_settings returns None when RERANKER=llm but no API key."""
        from mapper_copilot.config import Settings

        fake_settings = Settings(
            reranker="llm",
            anthropic_api_key=None,
        )
        monkeypatch.setattr("mapper_copilot.config.settings", fake_settings)

        reranker = create_reranker_from_settings()
        assert reranker is None

    def test_create_reranker_from_settings_llm_with_key(self, monkeypatch):
        """create_reranker_from_settings creates LLMReranker with API key."""
        from mapper_copilot.config import Settings

        fake_settings = Settings(
            reranker="llm",
            reranker_model="claude-opus-4-8",
            anthropic_api_key="test-api-key",
        )
        monkeypatch.setattr("mapper_copilot.config.settings", fake_settings)

        reranker = create_reranker_from_settings()
        assert isinstance(reranker, LLMReranker)
        assert reranker.model_id == "claude-opus-4-8"
        assert reranker._api_key == "test-api-key"

    def test_create_reranker_from_settings_local(self, monkeypatch):
        """create_reranker_from_settings creates LocalCrossEncoderReranker."""
        from mapper_copilot.config import Settings

        fake_settings = Settings(
            reranker="local",
            reranker_model="custom-cross-encoder",
        )
        monkeypatch.setattr("mapper_copilot.config.settings", fake_settings)

        reranker = create_reranker_from_settings()
        assert isinstance(reranker, LocalCrossEncoderReranker)
        assert reranker.model_name == "custom-cross-encoder"


class TestLocalCrossEncoderReranker:
    """Tests for LocalCrossEncoderReranker implementation."""

    def test_instantiation_with_defaults(self):
        """LocalCrossEncoderReranker instantiates with default model."""
        reranker = LocalCrossEncoderReranker()
        assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert reranker._model is None

    def test_instantiation_with_custom_model(self):
        """LocalCrossEncoderReranker accepts custom model name."""
        reranker = LocalCrossEncoderReranker(model_name="BAAI/bge-reranker-base")
        assert reranker.model_name == "BAAI/bge-reranker-base"

    def test_rerank_empty_candidates(self):
        """Rerank returns empty list for empty input."""
        reranker = LocalCrossEncoderReranker()
        result = reranker.rerank("test question", [], top_k=5)
        assert result == []

    def test_rerank_returns_top_k(self, monkeypatch):
        """Rerank returns exactly top_k candidates from larger pool."""
        # Mock the cross-encoder model
        mock_model = Mock()
        # Simulate scores: higher score for better match
        # Return scores for 10 candidates
        mock_model.predict.return_value = [0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.6, 0.4, 0.5, 0.15]

        reranker = LocalCrossEncoderReranker()
        reranker._model = mock_model  # Inject mock

        # Create 10 candidates
        candidates = [
            {"question": f"SLCP question {i}", "key": f"key-{i}", "section": "TEST"}
            for i in range(10)
        ]

        # Rerank to top 5
        result = reranker.rerank("RSC test question", candidates, top_k=5)

        # Should return exactly 5
        assert len(result) == 5

        # Should be sorted by score descending
        # Scores were: [0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.6, 0.4, 0.5, 0.15]
        # Top 5: 0.9 (idx 0), 0.8 (idx 2), 0.7 (idx 4), 0.6 (idx 6), 0.5 (idx 8)
        assert result[0]["key"] == "key-0"
        assert result[1]["key"] == "key-2"
        assert result[2]["key"] == "key-4"
        assert result[3]["key"] == "key-6"
        assert result[4]["key"] == "key-8"

        # Each result should have llm_rank and llm_score
        assert result[0]["llm_rank"] == 1
        assert result[0]["llm_score"] == 0.9
        assert result[1]["llm_rank"] == 2
        assert result[1]["llm_score"] == 0.8

    def test_rerank_adds_metadata_fields(self, monkeypatch):
        """Rerank adds llm_rank, llm_score, reason fields."""
        mock_model = Mock()
        mock_model.predict.return_value = [0.85, 0.75]

        reranker = LocalCrossEncoderReranker()
        reranker._model = mock_model

        candidates = [
            {"question": "Question 1", "key": "key-1", "section": "SECTION-A"},
            {"question": "Question 2", "key": "key-2", "section": "SECTION-B"},
        ]

        result = reranker.rerank("Test RSC question", candidates, top_k=2)

        # Check first result has all fields
        assert "llm_rank" in result[0]
        assert "llm_score" in result[0]
        assert "reason" in result[0]

        # Original fields preserved
        assert result[0]["key"] == "key-1"
        assert result[0]["question"] == "Question 1"
        assert result[0]["section"] == "SECTION-A"

    def test_rerank_preserves_original_candidate_fields(self, monkeypatch):
        """Rerank preserves all original candidate fields."""
        mock_model = Mock()
        mock_model.predict.return_value = [0.9]

        reranker = LocalCrossEncoderReranker()
        reranker._model = mock_model

        candidates = [
            {
                "question": "Test question",
                "key": "test-key",
                "section": "TEST SECTION",
                "subsection": "Test Subsection",
                "category": "Test Category",
                "number": "TEST-NUM-1",
                "embedding_score": 0.75,
                "custom_field": "custom_value",
            }
        ]

        result = reranker.rerank("RSC question", candidates, top_k=1)

        # All original fields should be preserved
        assert result[0]["key"] == "test-key"
        assert result[0]["section"] == "TEST SECTION"
        assert result[0]["subsection"] == "Test Subsection"
        assert result[0]["category"] == "Test Category"
        assert result[0]["number"] == "TEST-NUM-1"
        assert result[0]["embedding_score"] == 0.75
        assert result[0]["custom_field"] == "custom_value"

        # New fields added
        assert result[0]["llm_rank"] == 1
        assert result[0]["llm_score"] == 0.9
        assert "reason" in result[0]

    def test_rerank_with_fewer_candidates_than_top_k(self, monkeypatch):
        """Rerank handles case where candidates < top_k."""
        mock_model = Mock()
        mock_model.predict.return_value = [0.8, 0.6]

        reranker = LocalCrossEncoderReranker()
        reranker._model = mock_model

        # Only 2 candidates but requesting top_k=5
        candidates = [
            {"question": "Q1", "key": "k1", "section": "S1"},
            {"question": "Q2", "key": "k2", "section": "S2"},
        ]

        result = reranker.rerank("RSC Q", candidates, top_k=5)

        # Should return only 2 (all available)
        assert len(result) == 2
        assert result[0]["key"] == "k1"  # Higher score
        assert result[1]["key"] == "k2"

    def test_rerank_lazy_model_loading(self, monkeypatch):
        """Cross-encoder model is loaded lazily on first rerank."""
        # Mock the sentence_transformers import
        mock_cross_encoder_class = Mock()
        mock_model_instance = Mock()
        mock_model_instance.predict.return_value = [0.9]

        mock_cross_encoder_class.return_value = mock_model_instance

        # Mock the sentence_transformers module
        mock_st_module = SimpleNamespace(CrossEncoder=mock_cross_encoder_class)
        sys.modules['sentence_transformers'] = mock_st_module

        try:
            reranker = LocalCrossEncoderReranker(model_name="test-model")

            # Model should not be loaded yet
            assert reranker._model is None

            # Trigger loading by calling rerank
            candidates = [{"question": "Test", "key": "k1", "section": "S1"}]
            reranker.rerank("RSC Q", candidates, top_k=1)

            # Model should now be loaded
            assert reranker._model is not None
            mock_cross_encoder_class.assert_called_once_with("test-model")
        finally:
            # Clean up mock
            if 'sentence_transformers' in sys.modules:
                del sys.modules['sentence_transformers']

    def test_rerank_reason_field_format(self, monkeypatch):
        """Rerank reason field includes score."""
        mock_model = Mock()
        mock_model.predict.return_value = [0.876]

        reranker = LocalCrossEncoderReranker()
        reranker._model = mock_model

        candidates = [{"question": "Test", "key": "k1", "section": "S1"}]
        result = reranker.rerank("RSC Q", candidates, top_k=1)

        # Reason should mention score
        assert "0.876" in result[0]["reason"]
        assert "Cross-encoder" in result[0]["reason"] or "relevance" in result[0]["reason"]
