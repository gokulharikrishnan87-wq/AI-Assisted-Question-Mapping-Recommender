"""Streamlit UI for Mapper Copilot - Enhanced with SLCP Metadata."""

import json
import logging
import os
from pathlib import Path
from typing import Any, List, Dict, Optional
import hashlib

import openpyxl
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# Set environment for local embeddings BEFORE imports
os.environ['PROVIDER'] = 'local'
os.environ['EMBEDDING_MODEL_ID'] = 'all-MiniLM-L6-v2'
os.environ['EMBEDDING_DIMENSION'] = '384'

from mapper_copilot.core.suggester import Suggester
from mapper_copilot.providers.embeddings import create_embedding_provider_from_settings
from mapper_copilot.providers.llm import MockLLM
from mapper_copilot.providers.vector_store import NumpyVectorStore
from mapper_copilot.providers.rerankers import create_reranker_from_settings
from mapper_copilot.config import settings
from mapper_copilot.ui_helpers_inline import (
    inject_fonts,
    inject_css,
    render_rsc_card,
    render_empty_rerank_state,
    render_rerank_disabled_hint,
    render_reranked_header,
)
from mapper_copilot.ui_simple_render import render_result_card_simple

# Constants
DEFAULT_TOP_K = 5  # Show top 5 matches
CACHE_DIR = Path(".streamlit/cache")
RSC_QUESTIONS_FILE = "RSC Questions.xlsx"
SLCP_DICT_FILE = "slcp_data_dictionary.json"


def get_parent_question(number: str, slcp_metadata: Dict[str, Dict]) -> str:
    """Get parent question text for a sub-option number.

    Args:
        number: SLCP number (e.g., 'MS-PLA-16-9')
        slcp_metadata: SLCP metadata dictionary

    Returns:
        Parent question text if found, empty string otherwise
    """
    if not number or '-' not in number:
        return ""

    # Extract parent number (e.g., 'MS-PLA-16' from 'MS-PLA-16-9')
    parts = number.rsplit('-', 1)
    if len(parts) != 2:
        return ""

    parent_number = parts[0]

    # Find parent question in metadata
    for key, meta in slcp_metadata.items():
        if meta.get('number') == parent_number:
            return meta.get('question', '')

    return ""


def get_cache_file() -> Path:
    """Get cache file path for mappings."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / "rsc_mappings_enhanced.json"


def load_rsc_questions() -> List[Dict[str, str]]:
    """Load RSC questions from Excel file."""
    if not os.path.exists(RSC_QUESTIONS_FILE):
        st.error(f"RSC Questions file not found: {RSC_QUESTIONS_FILE}")
        return []

    wb = openpyxl.load_workbook(RSC_QUESTIONS_FILE)
    ws = wb.active

    questions = []
    headers = None

    for i, row in enumerate(ws.iter_rows(min_row=1, values_only=True)):
        if i == 0:
            headers = row
            continue
        if not any(row):
            continue

        question_dict = dict(zip(headers, row))
        questions.append(question_dict)

    return questions


def load_slcp_data() -> tuple[Dict[str, str], Dict[str, Dict]]:
    """Load SLCP questions and metadata."""
    if not os.path.exists(SLCP_DICT_FILE):
        st.error(f"SLCP data dictionary not found: {SLCP_DICT_FILE}")
        return {}, {}

    with open(SLCP_DICT_FILE) as f:
        data = json.load(f)

    slcp_questions = {}
    slcp_metadata = {}

    for key, value in data.items():
        if isinstance(value, dict) and "question" in value and value.get("question", "").strip():
            slcp_questions[key] = value.get("question", "")
            slcp_metadata[key] = {
                "key": key,
                "number": value.get("number", ""),
                "section": value.get("section", ""),
                "subsection": value.get("subsection", ""),
                "category": value.get("category", ""),
            }

    return slcp_questions, slcp_metadata


def load_cached_mappings() -> Optional[Dict]:
    """Load cached mappings if available."""
    cache_file = get_cache_file()
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    return None


def save_mappings_to_cache(mappings: Dict) -> None:
    """Save mappings to cache."""
    cache_file = get_cache_file()
    with open(cache_file, "w") as f:
        json.dump(mappings, f, indent=2)


def build_suggester(slcp_questions: Dict[str, str], slcp_metadata: Dict[str, Dict]) -> Suggester:
    """Build suggester with SLCP data, local embeddings, and hybrid retrieval."""
    from mapper_copilot.providers.retrieval import BM25Index, HybridRetriever

    embedder = create_embedding_provider_from_settings()
    llm = MockLLM()

    # Build vector store with full metadata
    slcp_texts = list(slcp_questions.values())
    slcp_embeddings = embedder.batch_embed(slcp_texts)

    metadata_list = [
        {
            "slcp_question": question,
            "key": key,
            "number": slcp_metadata[key].get("number", ""),
            "section": slcp_metadata[key].get("section", ""),
            "subsection": slcp_metadata[key].get("subsection", ""),
            "category": slcp_metadata[key].get("category", ""),
        }
        for key, question in slcp_questions.items()
    ]

    vector_store = NumpyVectorStore()
    vector_store.index(slcp_embeddings, metadata_list)

    # Build BM25 index for hybrid retrieval
    bm25_corpus = [
        f"{meta['key']} {meta['number']} {question}"
        for meta, (key, question) in zip(metadata_list, slcp_questions.items())
    ]
    doc_ids = list(range(len(slcp_questions)))
    bm25_index = BM25Index(bm25_corpus, doc_ids)

    # Create hybrid retriever
    retriever = HybridRetriever(
        embedding_provider=embedder,
        vector_store=vector_store,
        bm25_index=bm25_index,
        k_retrieve=settings.k_retrieve if hasattr(settings, 'k_retrieve') else 40,
        use_bm25=settings.use_bm25 if hasattr(settings, 'use_bm25') else True,
        section_prior_weight=settings.section_prior_weight if hasattr(settings, 'section_prior_weight') else 0.1,
    )

    return Suggester(
        embedding_provider=embedder,
        llm_provider=llm,
        retriever=retriever,  # Use hybrid retriever instead of direct vector_store
        top_k=DEFAULT_TOP_K,
    )


def map_all_rsc_questions(
    rsc_questions: List[Dict[str, str]],
    suggester: Suggester,
    slcp_questions: Dict[str, str],
    slcp_metadata: Dict[str, Dict],
    progress_bar: Any,
    status_text: Any,
) -> Dict[str, Dict]:
    """Map all RSC questions to SLCP with hybrid retrieval and enhanced metadata."""
    mappings = {}
    total = len(rsc_questions)

    for i, rsc_q in enumerate(rsc_questions):
        question_text = rsc_q.get("LLL Description", "")
        lll_key = rsc_q.get("LLL Key (unique)", f"RSC_{i}")

        if not question_text:
            continue

        try:
            # Build RSC metadata for hybrid retrieval
            rsc_metadata = {
                "section": rsc_q.get("Section", ""),
                "lll_key": lll_key,
                "reference_data": rsc_q.get("Reference Data", ""),
            }

            # Get candidates directly from hybrid retrieval (with full metadata & scores)
            if suggester.retriever:
                candidate_dicts = suggester.retriever.retrieve(question_text, rsc_metadata)
                # Store top 100 for Claude reranking (fits within token limits)
                # But only display top 5 in UI
                all_candidates = candidate_dicts[:100]  # Top 100 for Claude to search
                candidates = candidate_dicts[:5]  # Top 5 for display
            else:
                # Fallback to legacy path if no retriever
                result = suggester.suggest(question_text, rsc_metadata)
                # Convert to dict format
                candidates = []
                for candidate_text in result.source_candidates[:5]:
                    candidate_key = None
                    for key, question in slcp_questions.items():
                        if question == candidate_text:
                            candidate_key = key
                            break
                    candidate_meta = slcp_metadata.get(candidate_key, {}) if candidate_key else {}
                    candidates.append({
                        "question": candidate_text,
                        "key": candidate_meta.get("key", ""),
                        "number": candidate_meta.get("number", ""),
                        "section": candidate_meta.get("section", ""),
                        "embedding_score": 0.5,  # Default score
                    })

            # Get best match (first candidate)
            best_candidate = candidates[0] if candidates else {}

            mappings[lll_key] = {
                "rsc_question": question_text,
                "rsc_metadata": rsc_metadata,  # Store for on-demand reranking
                "section": rsc_q.get("Section", ""),
                "best_match": {
                    "question": best_candidate.get("question", ""),
                    "key": best_candidate.get("key", ""),
                    "number": best_candidate.get("number", ""),
                    "section": best_candidate.get("section", ""),
                    "subsection": best_candidate.get("subsection", ""),
                },
                "confidence": best_candidate.get("embedding_score", 0.5),
                "candidates": candidates,  # Top 5 for display
                "all_candidates": all_candidates if suggester.retriever else candidates,  # Top 100 for Claude
            }
        except Exception as e:
            logger.error(f"Error mapping {lll_key}: {e}", exc_info=True)
            mappings[lll_key] = {
                "rsc_question": question_text,
                "section": rsc_q.get("Section", ""),
                "error": str(e),
            }

        progress = (i + 1) / total
        progress_bar.progress(progress)
        status_text.text(f"Mapping {i + 1}/{total} questions...")

    return mappings


def render_mapping_result(mapping: Dict, index: int, key: str, reranker: Optional[Any], full_slcp_corpus: Optional[List[Dict]] = None, slcp_metadata: Optional[Dict[str, Dict]] = None) -> None:
    """Render a single mapping result with tab-based design."""
    confidence = mapping.get("confidence", 0)
    rsc_question = mapping.get("rsc_question", "")
    rsc_section = mapping.get("section", "")

    # Error handling
    if "error" in mapping:
        st.error(f"**{key}** — Error: {mapping['error']}")
        st.divider()
        return

    # Initialize rerank cache in session state
    if "rerank_cache" not in st.session_state:
        st.session_state.rerank_cache = {}

    # Header with confidence indicator
    if confidence >= 0.7:
        color = "🟢"
    elif confidence >= 0.5:
        color = "🟡"
    else:
        color = "🔵"

    col1, col2 = st.columns([0.1, 0.9])
    with col1:
        st.markdown(f"**{color}**")
    with col2:
        st.markdown(f"**{key}** — {rsc_section}")

    # Expandable details with tabs
    with st.expander(f"View mapping → {confidence:.0%}", expanded=False):
        # RSC question card
        render_rsc_card(rsc_question)

        # Get candidates for both tabs
        candidates = mapping.get("candidates", [])[:5]

        # Create tabs
        tab1, tab2 = st.tabs(["Semantic match", "Claude rerank"])

        # Tab 1: Semantic match (hybrid retrieval: BM25 + dense embeddings)
        with tab1:
            st.info("🔍 Results from Hybrid Retrieval (BM25 + Dense Embeddings)")
            if candidates:
                for i, candidate in enumerate(candidates):
                    # Get embedding score for this specific candidate
                    embedding_score = candidate.get("embedding_score", confidence)
                    score_pct = int(embedding_score * 100)

                    render_result_card_simple(
                        rank=i + 1,
                        slcp_key=candidate.get("key", ""),
                        number=candidate.get("number", ""),
                        section=candidate.get("section", ""),
                        question=candidate.get("question", ""),
                        score_pct=score_pct,
                        reason="",
                        is_top=(i == 0),
                    )
            else:
                st.info("No candidates found.")

        # Tab 2: Claude rerank
        with tab2:
            if reranker is None:
                # No reranker configured
                render_rerank_disabled_hint()
            elif key not in st.session_state.rerank_cache:
                # Empty state - show CTA and button
                # Check if using full corpus mode
                using_full_corpus = (
                    settings.reranker == "llm" and
                    reranker is not None and
                    hasattr(reranker, 'full_slcp_corpus') and
                    reranker.full_slcp_corpus and
                    full_slcp_corpus  # Make sure corpus is available
                )

                # Get the number of candidates Claude will search
                all_candidates_list = mapping.get("all_candidates", candidates)
                num_candidates = len(all_candidates_list)

                if using_full_corpus:
                    corpus_size = len(full_slcp_corpus) if full_slcp_corpus else len(reranker.full_slcp_corpus)
                    st.info(
                        f"💡 **Claude will search the full SLCP corpus** ({corpus_size} questions) "
                        f"independently of hybrid retrieval to find the best matches."
                    )
                    button_text = f"🔍 Search All {corpus_size} SLCP Questions with Claude"
                    spinner_text = f"Searching {corpus_size} SLCP questions with Claude…"
                elif num_candidates > 5:
                    # Using extended hybrid retrieval (top 100)
                    st.info(
                        f"💡 **Claude will search the top {num_candidates} candidates** from hybrid retrieval "
                        f"to find the best matches. (Much better than just reranking top 5!)"
                    )
                    button_text = f"🔍 Search Top {num_candidates} Candidates with Claude"
                    spinner_text = f"Searching {num_candidates} candidates with Claude…"
                else:
                    render_empty_rerank_state()
                    button_text = "Rerank with Claude"
                    spinner_text = "Reranking with Claude…"

                if st.button(button_text, key=f"rerank_{key}"):
                    with st.spinner(spinner_text):
                        try:
                            # Use top 100 candidates from hybrid retrieval for Claude to search
                            all_candidates_list = mapping.get("all_candidates", candidates)

                            # Prepare candidates for reranker
                            candidates_for_rerank = []
                            for cand in all_candidates_list:
                                candidates_for_rerank.append({
                                    "key": cand.get("key", ""),
                                    "number": cand.get("number", ""),
                                    "section": cand.get("section", ""),
                                    "question": cand.get("question", ""),
                                    "embedding_score": cand.get("embedding_score", confidence),
                                })

                            # Call reranker with top 100 candidates (or full corpus if configured)
                            results = reranker.rerank(
                                rsc_question,
                                candidates_for_rerank,
                                top_k=5
                            )

                            # Cache results
                            st.session_state.rerank_cache[key] = results
                            st.rerun()

                        except Exception as e:
                            st.error(f"Error during reranking: {str(e)}")
                            logger.error(f"Reranking failed for {key}: {e}")
            else:
                # Results cached - render them
                reranked_results = st.session_state.rerank_cache[key]

                # Check if full corpus mode was used
                using_full_corpus = (
                    settings.reranker == "llm" and
                    reranker is not None and
                    hasattr(reranker, 'full_slcp_corpus') and
                    reranker.full_slcp_corpus and
                    full_slcp_corpus  # Make sure corpus is available
                )

                # Get the number of candidates that were searched
                all_candidates_list = mapping.get("all_candidates", candidates)
                num_candidates = len(all_candidates_list)

                if using_full_corpus:
                    corpus_size = len(full_slcp_corpus) if full_slcp_corpus else len(reranker.full_slcp_corpus)
                    st.success(f"✅ **Claude searched {corpus_size} SLCP questions independently**")
                elif num_candidates > 5:
                    st.success(f"✅ **Claude searched the top {num_candidates} candidates and found the best matches**")
                else:
                    render_reranked_header(settings.reranker_model)

                for i, result in enumerate(reranked_results):
                    # Get LLM score (0.0-1.0) and convert to percentage
                    llm_score = result.get("llm_score", 0.0)
                    score_pct = int(llm_score * 100)

                    render_result_card_simple(
                        rank=i + 1,
                        slcp_key=result.get("key", ""),
                        number=result.get("number", ""),
                        section=result.get("section", ""),
                        question=result.get("question", ""),
                        score_pct=score_pct,
                        reason=result.get("reason", ""),
                        is_top=(i == 0),
                    )

    st.divider()


def render_all_mappings_section(mappings: Dict[str, Dict], reranker: Optional[Any], full_slcp_corpus: Optional[List[Dict]] = None, slcp_metadata: Optional[Dict[str, Dict]] = None) -> None:
    """Render all mappings with filters and export."""
    st.header("📊 All RSC to SLCP Mappings")

    # Stats
    total = len(mappings)
    errors = sum(1 for m in mappings.values() if "error" in m)
    success = total - errors

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Mappings", total)
    with col2:
        st.metric("Successful", success)
    with col3:
        st.metric("Errors", errors)
    with col4:
        avg_confidence = (
            sum(m.get("confidence", 0) for m in mappings.values() if "error" not in m)
            / success
            if success > 0
            else 0
        )
        st.metric("Avg Confidence", f"{avg_confidence:.1%}")

    st.divider()

    # Export option
    if st.button("📥 Export to CSV"):
        df_data = []
        for key, mapping in mappings.items():
            if "error" not in mapping:
                best = mapping.get("best_match", {})
                row = {
                    "RSC_Key": key,
                    "RSC_Section": mapping["section"],
                    "RSC_Question": mapping["rsc_question"],
                    "Best_SLCP_Key": best.get("key", ""),
                    "Best_SLCP_Number": best.get("number", ""),
                    "Best_SLCP_Section": best.get("section", ""),
                    "Best_SLCP_Subsection": best.get("subsection", ""),
                    "Best_SLCP_Question": best.get("question", ""),
                    "Confidence": mapping["confidence"],
                }

                # Add alternatives
                for i, candidate in enumerate(mapping.get("candidates", [])[:5], 1):
                    row[f"Alt_{i}_Key"] = candidate.get("key", "")
                    row[f"Alt_{i}_Number"] = candidate.get("number", "")
                    row[f"Alt_{i}_Section"] = candidate.get("section", "")
                    row[f"Alt_{i}_Question"] = candidate.get("question", "")

                df_data.append(row)

        if df_data:
            df = pd.DataFrame(df_data)
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="rsc_slcp_mappings_enhanced.csv",
                mime="text/csv",
            )

    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        filter_section = st.multiselect(
            "Filter by RSC Section",
            options=sorted(set(m.get("section", "") for m in mappings.values())),
            default=None,
        )

    with col2:
        min_confidence = st.slider(
            "Minimum Confidence",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.1,
        )

    st.divider()

    # Display mappings
    filtered_mappings = {
        k: v
        for k, v in mappings.items()
        if (
            (not filter_section or v.get("section", "") in filter_section)
            and v.get("confidence", 0) >= min_confidence
        )
    }

    if not filtered_mappings:
        st.info("No mappings match the selected filters.")
    else:
        st.info(f"Showing {len(filtered_mappings)} of {len(mappings)} mappings")

        for key, mapping in filtered_mappings.items():
            render_mapping_result(mapping, 0, key, reranker, full_slcp_corpus, slcp_metadata)


def main() -> None:
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Mapper Copilot - Enhanced",
        page_icon="🧠",
        layout="wide",
    )

    # Inject fonts and CSS once per session
    inject_fonts()
    inject_css()

    st.title("🧠 Mapper Copilot - RSC to SLCP Mapping")
    st.markdown("**Enhanced with SLCP Key, Number & Section metadata**")

    # Load data first (needed for reranker initialization)
    with st.spinner("Loading RSC questions..."):
        rsc_questions = load_rsc_questions()

    with st.spinner("Loading SLCP data dictionary..."):
        slcp_questions, slcp_metadata = load_slcp_data()

    # Build full SLCP corpus for LLM reranker
    full_slcp_corpus = []
    if slcp_questions and slcp_metadata:
        for key, question in slcp_questions.items():
            meta = slcp_metadata.get(key, {})
            full_slcp_corpus.append({
                "key": meta.get("key", key),
                "number": meta.get("number", ""),
                "section": meta.get("section", ""),
                "subsection": meta.get("subsection", ""),
                "category": meta.get("category", ""),
                "question": question,
            })

    # Initialize reranker (once, reused throughout)
    # NOTE: We use top 100 from hybrid retrieval instead of full corpus to stay within token limits
    reranker = None
    try:
        from mapper_copilot.providers.rerankers import create_reranker
        reranker = create_reranker(
            reranker_type=settings.reranker,
            model_id=settings.reranker_model,
            api_key=settings.anthropic_api_key,
            full_slcp_corpus=None,  # Don't use full corpus - use top 100 from hybrid retrieval instead
        )
    except Exception as e:
        logger.warning(f"Failed to initialize reranker: {e}")

    # Show configuration
    with st.expander("⚙️ Configuration", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Provider", settings.provider)
        with col2:
            st.metric("Model", settings.embedding_model_id)
        with col3:
            st.metric("Top Matches", DEFAULT_TOP_K)
        with col4:
            reranker_status = "✅ Enabled" if reranker is not None else "❌ Disabled"
            reranker_mode = ""
            if reranker is not None and settings.reranker == "llm":
                reranker_mode = " (Top 100 Search)"
            elif reranker is not None and settings.reranker == "local":
                reranker_mode = " (Cross-Encoder)"
            st.metric("Reranker", reranker_status + reranker_mode)

    st.divider()

    if not rsc_questions or not slcp_questions:
        st.error("Failed to load data files.")
        return

    st.success(f"✅ Loaded {len(rsc_questions)} RSC questions and {len(slcp_questions)} SLCP questions")

    # Check cache
    cached_mappings = load_cached_mappings()

    # Session state for mappings
    if "mappings" not in st.session_state:
        if cached_mappings:
            st.session_state.mappings = cached_mappings
            st.success(f"✅ Loaded {len(cached_mappings)} cached mappings")
        else:
            st.session_state.mappings = None

    # Mapping workflow
    if st.session_state.mappings is None:
        st.warning(
            f"⏱️ Ready to map {len(rsc_questions)} RSC questions"
        )

        st.info("💡 Enhanced format includes SLCP Key, Number, and Section for each match")

        if st.button("🚀 Start Mapping All Questions", key="start_mapping", use_container_width=True):
            with st.spinner("Building suggester with hybrid retrieval (BM25 + Dense Embeddings)..."):
                suggester = build_suggester(slcp_questions, slcp_metadata)

            st.success("✅ Hybrid retrieval ready! (BM25 + Local Embeddings)")

            # Create progress indicators
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Map all questions
            with st.spinner("Mapping questions..."):
                mappings = map_all_rsc_questions(
                    rsc_questions,
                    suggester,
                    slcp_questions,
                    slcp_metadata,
                    progress_bar,
                    status_text,
                )

            # Save to cache
            save_mappings_to_cache(mappings)
            st.session_state.mappings = mappings

            progress_bar.empty()
            status_text.empty()
            st.success(f"✅ Mapping complete! {len(mappings)} questions processed.")
            st.rerun()

    else:
        # Display all mappings
        render_all_mappings_section(st.session_state.mappings, reranker, full_slcp_corpus, slcp_metadata)

        # Reset option
        st.divider()
        if st.button("🔄 Clear Cache & Remap", use_container_width=True):
            get_cache_file().unlink(missing_ok=True)
            st.session_state.mappings = None
            st.rerun()


if __name__ == "__main__":
    main()
