"""Reranker provider implementations for refining candidate rankings."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Reranker(ABC):
    """Abstract base class for reranker providers."""

    @abstractmethod
    def rerank(self, rsc_question: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """Rerank candidates for an RSC question.

        Args:
            rsc_question: The RSC question text.
            candidates: List of candidate dicts with SLCP metadata (key, number, section,
                       subsection, question, embedding_score).
            top_k: Number of top candidates to return (default 5).

        Returns:
            Ranked list of candidate dicts with added fields: llm_rank, llm_score, reason.
        """
        pass


class LLMReranker(Reranker):
    """LLM-based reranker using Anthropic's Claude API.

    Synchronous reranking for single-question on-click interactions.
    Works independently of hybrid retrieval by searching the full SLCP corpus.
    """

    def __init__(
        self,
        model_id: str = "claude-sonnet-4-6",
        api_key: Optional[str] = None,
        full_slcp_corpus: Optional[List[Dict]] = None,
    ):
        """Initialize LLM reranker.

        Args:
            model_id: Claude model identifier (default: claude-sonnet-4-6).
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
            full_slcp_corpus: Full list of SLCP question dicts (all ~820 questions).
                            If provided, reranker searches this instead of candidates param.
        """
        self.model_id = model_id
        self._client = None
        self._api_key = api_key
        self.full_slcp_corpus = full_slcp_corpus or []

    def _get_client(self):
        """Lazily initialize Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic

                self._client = Anthropic(api_key=self._api_key)
            except ImportError:
                raise RuntimeError(
                    "anthropic package not installed. "
                    "Install with: pip install 'mapper-copilot[llm-reranker]'"
                )
        return self._client

    def rerank(self, rsc_question: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """Rerank candidates using Claude API.

        Args:
            rsc_question: The RSC question text.
            candidates: List of candidate dicts with SLCP metadata.
                       IGNORED if full_slcp_corpus was provided at init.
            top_k: Number of top candidates to return.

        Returns:
            Ranked list of candidates with llm_rank, llm_score, and reason fields.
        """
        # Use full corpus if available, otherwise use candidates
        search_corpus = self.full_slcp_corpus if self.full_slcp_corpus else candidates

        if not search_corpus:
            return []

        client = self._get_client()

        # Build listwise prompt
        use_full_corpus = bool(self.full_slcp_corpus)
        prompt = self._build_listwise_prompt(rsc_question, search_corpus, top_k, use_full_corpus)

        try:
            # Synchronous API call with temperature=0 for stable scoring
            response = client.messages.create(
                model=self.model_id,
                max_tokens=2048,  # Increased for longer responses with full corpus
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract response text
            response_text = response.content[0].text

            # Parse JSON response
            ranked_results = self._parse_response(response_text, search_corpus)

            return ranked_results

        except Exception as e:
            logger.warning(f"LLM reranking failed: {e}. Falling back to embedding order.")
            # Fall back to embedding order (use candidates, not full corpus)
            return self._fallback_to_embedding_order(candidates, top_k)

    def _build_listwise_prompt(
        self, rsc_question: str, candidates: List[Dict], top_k: int, use_full_corpus: bool = False
    ) -> str:
        """Build listwise reranking prompt."""
        candidates_text = []
        for i, cand in enumerate(candidates, 1):
            slcp_key = cand.get("key", "N/A")
            slcp_question = cand.get("question", "")
            slcp_section = cand.get("section", "N/A")
            candidates_text.append(
                f"{i}. [{slcp_key}] {slcp_section}\n   {slcp_question}"
            )

        candidates_formatted = "\n".join(candidates_text)

        # Different prompt for full corpus vs pre-filtered candidates
        if use_full_corpus:
            corpus_description = f"ALL SLCP Questions (complete corpus of {len(candidates)} questions)"
            task_description = f"""Task: Search through ALL SLCP questions and return the top {top_k} most relevant matches for the RSC question."""
        else:
            corpus_description = f"SLCP Candidate Questions (pre-filtered by hybrid retrieval)"
            task_description = f"""Task: Rerank these candidate questions and return the top {top_k} most relevant matches."""

        prompt = f"""You are a compliance mapping expert. Your task is to find the best SLCP question matches for an RSC question.

RSC Question:
{rsc_question}

{corpus_description}:
{candidates_formatted}

{task_description}

For each match, provide:
- slcp_key: The SLCP identifier (e.g., "hs-con-3x")
- score: Relevance score from 0.0 (irrelevant) to 1.0 (perfect match)
- reason: One short sentence explaining why this SLCP question matches the RSC question

Important:
- Return ONLY a JSON array, no markdown fences, no prose, no explanations outside the JSON
- Format: [{{"slcp_key": "...", "score": 0.9, "reason": "..."}}, ...]
- Order by relevance (best match first)
- Scores should reflect true relevance, not just ordinal ranking
- If searching the full corpus, you can recommend questions that may not be in the top candidates from automated retrieval

JSON array:"""

        return prompt

    def _parse_response(self, response_text: str, candidates: List[Dict]) -> List[Dict]:
        """Parse LLM response and merge with candidate metadata.

        Args:
            response_text: Raw LLM response text.
            candidates: Original candidate list.

        Returns:
            Ranked candidates with LLM scores and reasons.
        """
        # Strip markdown fences if present
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```"):
            lines = cleaned_text.split("\n")
            # Remove first and last lines if they're fences
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned_text = "\n".join(lines).strip()

        # Parse JSON
        try:
            ranked_items = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}. Response: {cleaned_text[:200]}")
            raise

        # Build lookup for candidates by key
        candidate_lookup = {cand.get("key"): cand for cand in candidates}

        # Merge LLM results with candidate metadata
        results = []
        for rank, item in enumerate(ranked_items, 1):
            slcp_key = item.get("slcp_key")
            if slcp_key in candidate_lookup:
                candidate = candidate_lookup[slcp_key].copy()
                candidate["llm_rank"] = rank
                candidate["llm_score"] = float(item.get("score", 0.0))
                candidate["reason"] = item.get("reason", "")
                results.append(candidate)

        return results

    def _fallback_to_embedding_order(self, candidates: List[Dict], top_k: int) -> List[Dict]:
        """Fall back to embedding order when LLM fails."""
        results = []
        for rank, cand in enumerate(candidates[:top_k], 1):
            candidate = cand.copy()
            candidate["llm_rank"] = rank
            candidate["llm_score"] = cand.get("embedding_score", 0.5)
            candidate["reason"] = "Fallback: using embedding similarity"
            results.append(candidate)
        return results


class LocalCrossEncoderReranker(Reranker):
    """Local cross-encoder reranker using sentence-transformers.

    Uses a cross-encoder model to jointly score (RSC question, SLCP candidate) pairs.
    More accurate than bi-encoder embeddings for final ranking, works fully offline.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """Initialize local cross-encoder reranker.

        Args:
            model_name: HuggingFace cross-encoder model name.
                       Default: cross-encoder/ms-marco-MiniLM-L-6-v2 (lightweight, offline).
                       Alternative: BAAI/bge-reranker-base (higher quality, larger).
        """
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        """Lazily initialize cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name)
                logger.info(f"Loaded cross-encoder model: {self.model_name}")
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers not installed. "
                    "Install with: pip install 'mapper-copilot[local-embeddings]'"
                )
        return self._model

    def rerank(self, rsc_question: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """Rerank candidates using local cross-encoder.

        Takes a pool of candidates (typically ~40 from hybrid retrieval) and
        returns the top-k (default 5) highest-scoring matches.

        Args:
            rsc_question: The RSC question text.
            candidates: List of candidate dicts with SLCP metadata.
                       Expected to be the fused pool from hybrid retrieval (~40 items).
            top_k: Number of top candidates to return (default 5).

        Returns:
            Ranked list of top-k candidates with llm_rank, llm_score fields added.
            (Note: Uses llm_score/llm_rank field names for compatibility with UI,
             even though this is a local cross-encoder, not an LLM.)
        """
        if not candidates:
            return []

        model = self._get_model()

        # Build (question, candidate) pairs
        pairs = []
        for cand in candidates:
            # Primary text is the SLCP question
            slcp_question = cand.get("question", "")

            # Build pair: (RSC question, SLCP question)
            # Keep it simple - just the question texts
            pair = (rsc_question, slcp_question)
            pairs.append(pair)

        # Score all pairs
        scores = model.predict(pairs)

        # Sort by score descending
        scored_candidates = list(zip(candidates, scores))
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Return top-k with metadata
        results = []
        for rank, (candidate, score) in enumerate(scored_candidates[:top_k], 1):
            result = candidate.copy()
            result["llm_rank"] = rank  # Using llm_rank for UI compatibility
            result["llm_score"] = float(score)

            # Generate a simple reason (cross-encoder doesn't provide explanations)
            result["reason"] = f"Cross-encoder relevance score: {score:.3f}"

            results.append(result)

        logger.info(f"Reranked {len(candidates)} candidates to top {len(results)}")
        return results


def create_reranker(
    reranker_type: str = "none",
    model_id: Optional[str] = None,
    api_key: Optional[str] = None,
    full_slcp_corpus: Optional[List[Dict]] = None,
) -> Optional[Reranker]:
    """Create a reranker instance.

    Args:
        reranker_type: Reranker type ('none', 'llm', or 'local').
        model_id: Model identifier (provider-specific).
        api_key: API key for LLM reranker (optional, reads from env if not provided).
        full_slcp_corpus: Full SLCP corpus for LLM reranker (all ~820 questions).
                         If provided, LLM reranker searches this instead of candidates.

    Returns:
        Configured reranker instance, or None if reranker_type is 'none' or API key missing.

    Raises:
        ValueError: If reranker_type is invalid.
    """
    if reranker_type == "none" or not reranker_type:
        return None
    elif reranker_type == "llm":
        # Require API key for LLM reranker
        if not api_key:
            logger.info("RERANKER=llm but no ANTHROPIC_API_KEY found. Reranking disabled.")
            return None
        if model_id is None:
            model_id = "claude-sonnet-4-6"
        return LLMReranker(
            model_id=model_id,
            api_key=api_key,
            full_slcp_corpus=full_slcp_corpus,
        )
    elif reranker_type == "local":
        if model_id is None:
            model_id = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        return LocalCrossEncoderReranker(model_name=model_id)
    else:
        raise ValueError(
            f"Invalid reranker type '{reranker_type}'. Must be 'none', 'llm', or 'local'"
        )


def create_reranker_from_settings() -> Optional[Reranker]:
    """Create reranker using global settings.

    Returns:
        Configured reranker based on settings.RERANKER, or None if disabled.
    """
    from mapper_copilot.config import settings

    return create_reranker(
        reranker_type=settings.reranker,
        model_id=settings.reranker_model,
        api_key=settings.anthropic_api_key,
    )
