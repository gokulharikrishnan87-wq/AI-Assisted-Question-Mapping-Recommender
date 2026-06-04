"""Two-stage RAG suggester orchestration."""

from __future__ import annotations

import logging
import re
from typing import List

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
        vector_store: VectorStore,
        top_k: int = 5,
    ):
        """Initialize suggester with providers."""
        self.embedding_provider = embedding_provider
        self.llm_provider = llm_provider
        self.vector_store = vector_store
        self.top_k = top_k

    def suggest(self, rsc_question: str) -> Mapping:
        """Suggest SLCP mapping for an RSC question."""
        logger.info("Generating mapping suggestion")
        embedding = self.embedding_provider.embed(rsc_question)
        results = self.vector_store.query(embedding, top_k=self.top_k)
        candidates = [
            candidate
            for candidate in (
                self._extract_candidate_question(metadata) for metadata, _score in results
            )
            if candidate
        ]

        if not candidates:
            logger.warning("No vector store candidates found for suggestion")
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
        for key in ("question", "slcp_question", "description"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
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
