"""Hybrid retrieval combining dense embeddings and BM25 lexical matching."""

import logging
import re
from typing import Dict, List, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

from mapper_copilot.providers.embeddings import EmbeddingProvider
from mapper_copilot.providers.vector_store import VectorStore

logger = logging.getLogger(__name__)


def tokenize_preserving_codes(text: str) -> List[str]:
    """Tokenize text while preserving numbers and codes.

    Lowercase for normalization, but keep numbers intact (e.g., "15" vs "18").
    Preserve codes like "FP-STE-1", "ms-6-3x", "HS-CON-3".

    Args:
        text: Input text to tokenize.

    Returns:
        List of tokens.
    """
    if not text:
        return []

    # Lowercase but preserve structure
    text = text.lower()

    # Split on whitespace and punctuation, but keep hyphens in codes
    # Pattern: split on spaces, commas, periods (but not hyphens within alphanumeric sequences)
    tokens = re.findall(r'\b[\w-]+\b', text)

    # Filter out very short tokens (single chars) unless they're numbers
    tokens = [t for t in tokens if len(t) > 1 or t.isdigit()]

    return tokens


def reciprocal_rank_fusion(
    ranked_lists: List[List[int]],
    k: int = 60
) -> List[int]:
    """Fuse multiple ranked lists using Reciprocal Rank Fusion.

    RRF score for document d = sum over all lists of: 1 / (k + rank(d))

    Args:
        ranked_lists: List of ranked document ID lists (higher rank = earlier in list).
        k: Constant for RRF formula (default 60, standard value).

    Returns:
        Fused ranking as list of document IDs, sorted by RRF score descending.
    """
    if not ranked_lists:
        return []

    # Calculate RRF scores
    rrf_scores: Dict[int, float] = {}

    for ranked_list in ranked_lists:
        for rank, doc_id in enumerate(ranked_list):
            # rank is 0-indexed, so rank+1 is the actual position
            score = 1.0 / (k + rank + 1)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + score

    # Sort by score descending
    sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    return [doc_id for doc_id, score in sorted_docs]


class BM25Index:
    """BM25 lexical index for sparse retrieval."""

    def __init__(self, corpus_texts: List[str], doc_ids: List[int]):
        """Build BM25 index over corpus.

        Args:
            corpus_texts: List of text strings to index.
            doc_ids: Corresponding document IDs (indices).
        """
        if len(corpus_texts) != len(doc_ids):
            raise ValueError("corpus_texts and doc_ids must have same length")

        self.doc_ids = doc_ids

        # Tokenize corpus
        tokenized_corpus = [tokenize_preserving_codes(text) for text in corpus_texts]

        # Build BM25 index
        self.bm25 = BM25Okapi(tokenized_corpus)

        logger.info(f"Built BM25 index over {len(corpus_texts)} documents")

    def query(self, query_text: str, top_k: int = 40) -> List[Tuple[int, float]]:
        """Retrieve top-k documents for query.

        Args:
            query_text: Query string.
            top_k: Number of results to return.

        Returns:
            List of (doc_id, score) tuples, sorted by score descending.
        """
        tokenized_query = tokenize_preserving_codes(query_text)

        # Get BM25 scores for all documents
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        # Return (doc_id, score) pairs
        results = [(self.doc_ids[idx], float(scores[idx])) for idx in top_indices]

        return results


class HybridRetriever:
    """Hybrid retrieval combining dense embeddings and BM25."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        k_retrieve: int = 40,
        use_bm25: bool = True,
        section_prior_weight: float = 0.1,
    ):
        """Initialize hybrid retriever.

        Args:
            embedding_provider: Dense embedding provider.
            vector_store: Vector store for dense retrieval.
            bm25_index: BM25 index for lexical retrieval.
            k_retrieve: Number of candidates to retrieve (default 40).
            use_bm25: Whether to use BM25 (default True).
            section_prior_weight: Weight for same-section boost (default 0.1, 0 to disable).
        """
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.k_retrieve = k_retrieve
        self.use_bm25 = use_bm25
        self.section_prior_weight = section_prior_weight

    def retrieve(
        self,
        rsc_question: str,
        rsc_metadata: Dict[str, str]
    ) -> List[Dict]:
        """Retrieve and fuse candidates using hybrid retrieval.

        Args:
            rsc_question: RSC question text.
            rsc_metadata: RSC metadata dict with keys: section, lll_key, reference_data.

        Returns:
            List of candidate dicts with SLCP metadata and scores.
        """
        # 1. Dense retrieval
        embedding = self.embedding_provider.embed(rsc_question)
        dense_results = self.vector_store.query(embedding, top_k=self.k_retrieve)

        # Extract doc IDs from dense results (indices in vector store)
        dense_doc_ids = [i for i, (metadata, score) in enumerate(dense_results)]

        # 2. BM25 retrieval (if enabled)
        if self.use_bm25:
            # Build BM25 query from question + key + reference snippets
            bm25_query = self._build_bm25_query(rsc_question, rsc_metadata)
            bm25_results = self.bm25_index.query(bm25_query, top_k=self.k_retrieve)
            bm25_doc_ids = [doc_id for doc_id, score in bm25_results]
        else:
            bm25_doc_ids = []

        # 3. Fuse with RRF
        if bm25_doc_ids:
            fused_doc_ids = reciprocal_rank_fusion([dense_doc_ids, bm25_doc_ids])
        else:
            fused_doc_ids = dense_doc_ids

        # 4. Apply section prior (soft boost, not hard filter)
        if self.section_prior_weight > 0:
            fused_doc_ids = self._apply_section_prior(
                fused_doc_ids,
                rsc_metadata.get("section", ""),
                dense_results
            )

        # 5. Build candidate dicts with metadata
        candidates = []
        for doc_id in fused_doc_ids[:self.k_retrieve]:
            # Get metadata from dense results (vector store has full metadata)
            if doc_id < len(dense_results):
                metadata, dense_score = dense_results[doc_id]

                candidate = {
                    "key": metadata.get("key", ""),
                    "number": metadata.get("number", ""),
                    "section": metadata.get("section", ""),
                    "subsection": metadata.get("subsection", ""),
                    "category": metadata.get("category", ""),
                    "question": metadata.get("slcp_question", metadata.get("question", "")),
                    "embedding_score": float(dense_score),
                }
                candidates.append(candidate)

        logger.info(f"Retrieved {len(candidates)} fused candidates (dense + BM25)")
        return candidates

    def _build_bm25_query(self, rsc_question: str, rsc_metadata: Dict[str, str]) -> str:
        """Build BM25 query from RSC question and metadata.

        Args:
            rsc_question: RSC question text.
            rsc_metadata: RSC metadata dict.

        Returns:
            Combined query string for BM25.
        """
        query_parts = [rsc_question]

        # Add LLL key for exact code matching
        if rsc_metadata.get("lll_key"):
            query_parts.append(rsc_metadata["lll_key"])

        # Add first 200 chars of reference data for citation/code matching
        if rsc_metadata.get("reference_data"):
            ref_snippet = rsc_metadata["reference_data"][:200]
            query_parts.append(ref_snippet)

        return " ".join(query_parts)

    def _apply_section_prior(
        self,
        fused_doc_ids: List[int],
        rsc_section: str,
        dense_results: List[Tuple[Dict, float]]
    ) -> List[int]:
        """Apply soft section prior boost to same-section candidates.

        Args:
            fused_doc_ids: Fused document IDs.
            rsc_section: RSC section string (e.g., "1. Business Ethics").
            dense_results: Dense retrieval results with metadata.

        Returns:
            Re-ranked document IDs with section boost applied.
        """
        if not rsc_section:
            return fused_doc_ids

        # Extract numeric prefix from RSC section (e.g., "1. Business Ethics" -> "1")
        rsc_section_num = self._extract_section_number(rsc_section)

        # Build section map
        doc_sections = {}
        for i, (metadata, score) in enumerate(dense_results):
            slcp_section = metadata.get("section", "")
            doc_sections[i] = slcp_section

        # Boost same-section candidates by moving them up in ranking
        # Use a simple heuristic: if RSC section number matches any part of SLCP section,
        # or if section names are similar, give it a boost
        same_section_docs = []
        other_docs = []

        for doc_id in fused_doc_ids:
            slcp_section = doc_sections.get(doc_id, "")

            # Check for section match (fuzzy)
            if self._sections_match(rsc_section, rsc_section_num, slcp_section):
                same_section_docs.append(doc_id)
            else:
                other_docs.append(doc_id)

        # Interleave: boost same-section but don't hard filter
        # Strategy: for every 2 same-section, add 8 others (10% boost)
        result = []
        same_idx = 0
        other_idx = 0

        while same_idx < len(same_section_docs) or other_idx < len(other_docs):
            # Add boosted same-section candidates
            boost_count = max(1, int(10 * self.section_prior_weight))
            for _ in range(boost_count):
                if same_idx < len(same_section_docs):
                    result.append(same_section_docs[same_idx])
                    same_idx += 1

            # Add other candidates
            other_count = 10 - boost_count
            for _ in range(other_count):
                if other_idx < len(other_docs):
                    result.append(other_docs[other_idx])
                    other_idx += 1

        return result

    @staticmethod
    def _extract_section_number(rsc_section: str) -> str:
        """Extract numeric prefix from RSC section.

        Args:
            rsc_section: RSC section string (e.g., "1. Business Ethics").

        Returns:
            Section number (e.g., "1").
        """
        match = re.match(r'^(\d+)', rsc_section)
        return match.group(1) if match else ""

    @staticmethod
    def _sections_match(rsc_section: str, rsc_section_num: str, slcp_section: str) -> bool:
        """Check if RSC and SLCP sections match (fuzzy).

        Args:
            rsc_section: Full RSC section (e.g., "1. Business Ethics").
            rsc_section_num: Extracted number (e.g., "1").
            slcp_section: SLCP section (e.g., "MANAGEMENT SYSTEMS").

        Returns:
            True if sections are related.
        """
        if not slcp_section:
            return False

        # Lowercase for comparison
        rsc_lower = rsc_section.lower()
        slcp_lower = slcp_section.lower()

        # Check for keyword overlap
        # Extract meaningful words from both (ignore "and", "the", etc.)
        rsc_keywords = set(re.findall(r'\b\w{4,}\b', rsc_lower))
        slcp_keywords = set(re.findall(r'\b\w{4,}\b', slcp_lower))

        # If any keyword overlaps, consider it a match
        if rsc_keywords & slcp_keywords:
            return True

        # Section-specific mappings (domain knowledge)
        section_mappings = {
            "business ethics": ["management", "compliance"],
            "health": ["health", "safety"],
            "safety": ["health", "safety"],
            "labor": ["worker", "employment", "recruitment"],
            "wage": ["wage", "benefit", "compensation"],
            "working hours": ["working", "hours", "time"],
            "discrimination": ["treatment", "equality"],
            "environment": ["environment", "sustainability"],
        }

        for rsc_key, slcp_keys in section_mappings.items():
            if rsc_key in rsc_lower:
                for slcp_key in slcp_keys:
                    if slcp_key in slcp_lower:
                        return True

        return False
