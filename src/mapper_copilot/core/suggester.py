"""Two-stage RAG suggester orchestration."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from mapper_copilot.models import Mapping
from mapper_copilot.providers.embeddings import EmbeddingProvider
from mapper_copilot.providers.llm import LLMProvider
from mapper_copilot.providers.vector_store import Metadata, VectorStore

logger = logging.getLogger(__name__)


class Suggester:
    """Coordinate retrieval and ranking for RSC to SLCP suggestions."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        llm_provider: LLMProvider,
        vector_store: Optional[VectorStore] = None,
        top_k: int = 5,
        retriever=None,  # HybridRetriever instance (optional)
        reranker=None,  # Reranker instance (optional)
    ):
        """Initialize suggester with providers.

        Args:
            embedding_provider: Embedding provider for encoding questions.
            llm_provider: LLM provider for generating final responses.
            vector_store: Vector store (legacy, for backward compatibility).
            top_k: Number of top candidates to return (default 5).
            retriever: HybridRetriever instance (optional, new architecture).
            reranker: Reranker instance (optional, for post-retrieval reranking).
        """
        self.embedding_provider = embedding_provider
        self.llm_provider = llm_provider
        self.vector_store = vector_store
        self.top_k = top_k
        self.retriever = retriever
        self.reranker = reranker

    def suggest(
        self,
        rsc_question: str,
        rsc_metadata: Optional[Dict[str, str]] = None,
    ) -> Mapping:
        """Suggest SLCP mapping for an RSC question.

        Args:
            rsc_question: The RSC question text.
            rsc_metadata: Optional RSC metadata dict with keys:
                         section, lll_key, reference_data (for hybrid retrieval).

        Returns:
            Mapping with suggested SLCP match and candidates.
        """
        logger.info("Generating mapping suggestion")

        # Use new hybrid retrieval path if available
        if self.retriever is not None:
            candidates = self._retrieve_with_hybrid(rsc_question, rsc_metadata or {})
        else:
            # Fall back to legacy dense-only retrieval
            candidates = self._retrieve_with_legacy(rsc_question)

        if not candidates:
            logger.warning("No candidates found for suggestion")
            return Mapping(
                rsc_question=rsc_question,
                mapped_to="",
                confidence=0.0,
                rule="",
                source_candidates=[],
            )

        prompt = self._build_prompt(rsc_question, candidates)
        response = self.llm_provider.generate(prompt)

        return Mapping(
            rsc_question=rsc_question,
            mapped_to=self._extract_best_match(response, candidates),
            confidence=self._extract_confidence(response),
            rule=self._extract_rule(response),
            source_candidates=candidates,
        )

    def _retrieve_with_hybrid(
        self, rsc_question: str, rsc_metadata: Dict[str, str]
    ) -> List[str]:
        """Retrieve candidates using hybrid retrieval + optional reranking.

        Args:
            rsc_question: RSC question text.
            rsc_metadata: RSC metadata (section, lll_key, reference_data).

        Returns:
            List of candidate SLCP question strings.
        """
        # Step 1: Hybrid retrieval (dense + BM25 fusion) -> ~40 candidates
        candidate_dicts = self.retriever.retrieve(rsc_question, rsc_metadata)

        # Step 2: Optional reranking (cross-encoder or LLM) -> top 5
        if self.reranker is not None:
            candidate_dicts = self.reranker.rerank(
                rsc_question, candidate_dicts, top_k=self.top_k
            )
        else:
            # No reranker: just take top-k from hybrid retrieval
            candidate_dicts = candidate_dicts[: self.top_k]

        # Step 3: Extract question strings for LLM prompt
        candidates = [
            self._extract_candidate_from_dict(cand) for cand in candidate_dicts
        ]
        return [c for c in candidates if c]

    def _retrieve_with_legacy(self, rsc_question: str) -> List[str]:
        """Legacy dense-only retrieval using vector store.

        Args:
            rsc_question: RSC question text.

        Returns:
            List of candidate SLCP question strings.
        """
        embedding = self.embedding_provider.embed(rsc_question)
        results = self.vector_store.query(embedding, top_k=self.top_k)
        candidates = [
            candidate
            for candidate in (
                self._extract_candidate_question(metadata) for metadata, _score in results
            )
            if candidate
        ]
        return candidates

    def suggest_batch(self, rsc_questions: List[str]) -> List[Mapping]:
        """Suggest mappings for multiple RSC questions."""
        return [self.suggest(question) for question in rsc_questions]

    def _build_prompt(self, rsc_question: str, candidates: List[str]) -> str:
        candidate_lines = [
            f"{index}. {candidate}" for index, candidate in enumerate(candidates, start=1)
        ]
        candidate_block = "\n".join(candidate_lines)
        return (
            f"RSC Question: {rsc_question}\n\n"
            "Candidate SLCP Questions:\n"
            f"{candidate_block}\n\n"
            "Rank the best match and provide a mapping rule (one sentence)."
        )

    @staticmethod
    def _extract_candidate_question(metadata: Metadata) -> str:
        """Extract question text from legacy metadata dict."""
        for key in ("question", "slcp_question", "description"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _extract_candidate_from_dict(candidate_dict: Dict) -> str:
        """Extract question text from new candidate dict format.

        Args:
            candidate_dict: Candidate dict with keys: key, number, section, question, etc.

        Returns:
            Question text string.
        """
        question = candidate_dict.get("question", "")
        if isinstance(question, str) and question.strip():
            return question.strip()
        return ""

    @staticmethod
    def _extract_best_match(response: str, candidates: List[str]) -> str:
        lowered_response = response.lower()
        for candidate in candidates:
            if candidate.lower() in lowered_response:
                return candidate
        return candidates[0]

    @staticmethod
    def _extract_confidence(response: str) -> float:
        lowered_response = response.lower()
        if "high" in lowered_response:
            return 0.8
        if "medium" in lowered_response:
            return 0.5
        if "low" in lowered_response:
            return 0.3
        return 0.5

    @staticmethod
    def _extract_rule(response: str) -> str:
        sentences = [
            sentence.strip()
            for sentence in re.findall(r"[^.!?]+[.!?]?", response)
            if sentence.strip()
        ]
        if not sentences:
            return ""
        return sentences[-1]
