"""Streamlit UI for Mapper Copilot - Batch RSC to SLCP mapping with caching."""

import json
import os
from pathlib import Path
from typing import Any, List, Dict, Optional
import hashlib

import openpyxl
import pandas as pd
import streamlit as st

from mapper_copilot.core.suggester import Suggester
from mapper_copilot.providers.embeddings import create_embedding_provider_from_settings
from mapper_copilot.providers.llm import MockLLM
from mapper_copilot.providers.vector_store import NumpyVectorStore

# Constants
DEFAULT_TOP_K = 3
CACHE_DIR = Path(".streamlit/cache")
RSC_QUESTIONS_FILE = "RSC Questions.xlsx"
SLCP_DICT_FILE = "slcp_data_dictionary.json"


# ============================================================================
# CACHING & DATA LOADING
# ============================================================================


def get_cache_file() -> Path:
    """Get cache file path for mappings."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / "rsc_mappings_cache.json"


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
        if not any(row):  # Skip empty rows
            continue
        
        question_dict = dict(zip(headers, row))
        questions.append(question_dict)
    
    return questions


def load_slcp_questions() -> List[Dict[str, str]]:
    """Load SLCP questions from JSON with full metadata.

    Returns:
        List of SLCP metadata dicts with keys: key, number, section, subsection,
        category, question.
    """
    if not os.path.exists(SLCP_DICT_FILE):
        st.error(f"SLCP data dictionary not found: {SLCP_DICT_FILE}")
        return []

    with open(SLCP_DICT_FILE) as f:
        data = json.load(f)

    # Extract full metadata for each question
    slcp_metadata = []
    for key, value in data.items():
        if isinstance(value, dict) and "question" in value and value.get("question", "").strip():
            slcp_metadata.append({
                "key": key,
                "number": value.get("number", ""),
                "section": value.get("section", ""),
                "subsection": value.get("subsection", ""),
                "category": value.get("category", ""),
                "question": value.get("question", "").strip(),
            })

    return slcp_metadata


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


def get_cache_hash(rsc_questions: List[Dict]) -> str:
    """Generate hash of RSC questions to detect changes."""
    content = json.dumps(rsc_questions, sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()


# ============================================================================
# SUGGESTER INITIALIZATION
# ============================================================================


def build_suggester(slcp_metadata: List[Dict[str, str]]) -> Suggester:
    """Build suggester with hybrid retrieval and optional reranking.

    Args:
        slcp_metadata: List of SLCP metadata dicts (key, number, section, question, etc.).

    Returns:
        Configured Suggester instance with hybrid retrieval.
    """
    from mapper_copilot.config import settings
    from mapper_copilot.providers.retrieval import BM25Index, HybridRetriever
    from mapper_copilot.providers.rerankers import create_reranker

    embedder = create_embedding_provider_from_settings()
    llm = MockLLM()

    # Extract question texts for embedding
    slcp_texts = [meta["question"] for meta in slcp_metadata]
    slcp_embeddings = embedder.batch_embed(slcp_texts)

    # Build vector store with full metadata
    # Use "slcp_question" as key for backward compatibility with suggester
    metadata_list = [
        {
            "slcp_question": meta["question"],
            "key": meta["key"],
            "number": meta["number"],
            "section": meta["section"],
            "subsection": meta.get("subsection", ""),
            "category": meta.get("category", ""),
        }
        for meta in slcp_metadata
    ]

    vector_store = NumpyVectorStore()
    vector_store.index(slcp_embeddings, metadata_list)

    # Build BM25 index for hybrid retrieval
    # BM25 corpus: Include codes/numbers for exact matching
    bm25_corpus = [
        f"{meta['key']} {meta['number']} {meta['question']}"
        for meta in slcp_metadata
    ]
    doc_ids = list(range(len(slcp_metadata)))
    bm25_index = BM25Index(bm25_corpus, doc_ids)

    # Create hybrid retriever
    retriever = HybridRetriever(
        embedding_provider=embedder,
        vector_store=vector_store,
        bm25_index=bm25_index,
        k_retrieve=settings.k_retrieve,
        use_bm25=settings.use_bm25,
        section_prior_weight=settings.section_prior_weight,
    )

    # Create optional reranker
    reranker = create_reranker(
        reranker_type=settings.reranker,
        model_id=(
            settings.cross_encoder_model
            if settings.reranker == "local"
            else settings.reranker_model
        ),
        api_key=settings.anthropic_api_key,
    )

    return Suggester(
        embedding_provider=embedder,
        llm_provider=llm,
        retriever=retriever,
        reranker=reranker,
        top_k=DEFAULT_TOP_K,
    )


# ============================================================================
# BATCH MAPPING
# ============================================================================


def map_all_rsc_questions(
    rsc_questions: List[Dict[str, str]],
    suggester: Suggester,
    progress_bar: Any,
    status_text: Any,
) -> Dict[str, Dict]:
    """Map all RSC questions to SLCP using hybrid retrieval.

    Args:
        rsc_questions: List of RSC question dicts.
        suggester: Suggester instance (with hybrid retrieval enabled).
        progress_bar: Streamlit progress bar.
        status_text: Streamlit status text element.

    Returns:
        Dict mapping RSC keys to mapping results.
    """
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

            # Get hybrid retrieval candidates (no reranking yet - that's on-demand)
            if suggester.retriever:
                # Use hybrid retrieval directly to get candidates with metadata
                candidate_dicts = suggester.retriever.retrieve(question_text, rsc_metadata)
                # Take top 5 from hybrid retrieval
                candidate_dicts = candidate_dicts[:5]
            else:
                # Fallback: use suggester (won't have detailed metadata)
                result = suggester.suggest(question_text, rsc_metadata=rsc_metadata)
                # Convert to dict format
                candidate_dicts = [{"question": cand} for cand in result.source_candidates[:5]]

            mappings[lll_key] = {
                "rsc_question": question_text,
                "rsc_metadata": rsc_metadata,  # Store for on-demand reranking
                "section": rsc_q.get("Section", ""),
                "candidates": candidate_dicts,  # Full candidate dicts with scores
                "reranked": False,  # Track if Claude API was used
            }
        except Exception as e:
            mappings[lll_key] = {
                "rsc_question": question_text,
                "section": rsc_q.get("Section", ""),
                "error": str(e),
            }

        # Update progress
        progress = (i + 1) / total
        progress_bar.progress(progress)
        status_text.text(f"Mapping {i + 1}/{total} questions...")

    return mappings


# ============================================================================
# UI RENDERING
# ============================================================================


def render_mapping_result(mapping: Dict, index: int, key: str) -> None:
    """Render a single mapping result with expandable details and on-demand reranking."""

    if "error" in mapping:
        color = "🔴"
        status = "Error"
    else:
        # Determine status based on whether reranked
        if mapping.get("reranked"):
            color = "🟢"
            status = "Reranked with Claude"
        else:
            color = "🔵"
            status = "Hybrid Retrieval"

    # Header with key and status
    col1, col2 = st.columns([0.1, 0.9])
    with col1:
        st.markdown(f"**{color}**")
    with col2:
        st.markdown(f"**{key}** — {mapping.get('section', '')}")

    # RSC Question (full text)
    st.markdown(f"**RSC Question:** {mapping['rsc_question']}")

    # Expandable details
    with st.expander(f"View candidates → {status}"):
        if "error" in mapping:
            st.error(f"Error: {mapping['error']}")
        else:
            # Check if candidates are in old format (strings) or new format (dicts)
            candidates = mapping.get("candidates", [])
            if not candidates:
                st.warning("No candidates found")
                return

            # Check format of first candidate
            is_old_format = isinstance(candidates[0], str)

            if is_old_format:
                # Old cached format - show warning
                st.warning("⚠️ This data is from an old cache format. Please click 'Clear Cache & Remap' to see full candidate details and enable Claude reranking.")
                st.markdown("### Candidates (Legacy Format)")
                for i, candidate in enumerate(candidates, 1):
                    st.markdown(f"**{i}.** {candidate}")
                return

            # New format - display candidates with full details
            if candidates:
                st.markdown("### Top 5 SLCP Candidates")

                # Show reranking status
                if mapping.get("reranked"):
                    st.info("✅ These candidates were reranked using Claude API")
                else:
                    st.info("🔍 These candidates are from Hybrid Retrieval (BM25 + Dense Embeddings)")

                # Display candidates
                for i, candidate in enumerate(candidates, 1):
                    # Extract candidate details
                    slcp_key = candidate.get("key", "N/A")
                    slcp_number = candidate.get("number", "N/A")
                    slcp_section = candidate.get("section", "N/A")
                    slcp_question = candidate.get("question", "N/A")

                    # Get score (embedding_score for hybrid, llm_score for reranked)
                    if mapping.get("reranked"):
                        score = candidate.get("llm_score", 0)
                        reason = candidate.get("reason", "")
                        score_label = "Claude Score"
                    else:
                        score = candidate.get("embedding_score", 0)
                        reason = ""
                        score_label = "Similarity"

                    # Render candidate card
                    st.markdown(f"**{i}. [{slcp_key}]** `{slcp_number}` — Score: {score:.3f}")
                    st.markdown(f"   *{slcp_section}*")
                    st.markdown(f"   {slcp_question}")
                    if reason:
                        st.markdown(f"   💡 *{reason}*")
                    st.markdown("")

                # On-demand Claude reranking button
                if not mapping.get("reranked"):
                    st.divider()
                    if st.button(f"🤖 Rerank with Claude API", key=f"rerank_{key}", use_container_width=True):
                        # Perform reranking
                        with st.spinner("Reranking with Claude API..."):
                            try:
                                # Import here to avoid loading if not needed
                                from mapper_copilot.providers.rerankers import LLMReranker
                                from mapper_copilot.config import settings

                                # Create LLM reranker
                                reranker = LLMReranker(
                                    model_id=settings.reranker_model,
                                    api_key=settings.anthropic_api_key
                                )

                                # Rerank candidates
                                reranked_candidates = reranker.rerank(
                                    mapping["rsc_question"],
                                    mapping["candidates"],
                                    top_k=5
                                )

                                # Update mapping with reranked results
                                mapping["candidates"] = reranked_candidates
                                mapping["reranked"] = True

                                # Update in session state
                                st.session_state.mappings[key] = mapping

                                # Save to cache
                                save_mappings_to_cache(st.session_state.mappings)

                                st.success("✅ Reranked with Claude!")
                                st.rerun()

                            except Exception as e:
                                st.error(f"❌ Reranking failed: {e}")

    st.divider()


def render_all_mappings_section(mappings: Dict[str, Dict]) -> None:
    """Render all mappings with filters and export."""
    st.header("📊 All RSC to SLCP Mappings")
    
    # Stats
    total = len(mappings)
    errors = sum(1 for m in mappings.values() if "error" in m)
    success = total - errors
    reranked_count = sum(1 for m in mappings.values() if m.get("reranked", False))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Questions", total)
    with col2:
        st.metric("Successful", success)
    with col3:
        st.metric("Reranked with Claude", reranked_count)
    with col4:
        st.metric("Errors", errors)
    
    st.divider()
    
    # Export option
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Export to CSV"):
            df_data = []
            for key, mapping in mappings.items():
                if "error" not in mapping and mapping.get("candidates"):
                    # Get top candidate
                    top_candidate = mapping["candidates"][0] if mapping["candidates"] else {}

                    # Get score (llm_score if reranked, else embedding_score)
                    if mapping.get("reranked"):
                        score = top_candidate.get("llm_score", 0)
                        score_type = "Claude Score"
                    else:
                        score = top_candidate.get("embedding_score", 0)
                        score_type = "Similarity Score"

                    df_data.append({
                        "RSC_Key": key,
                        "RSC_Question": mapping["rsc_question"],
                        "Section": mapping["section"],
                        "Top_SLCP_Key": top_candidate.get("key", ""),
                        "Top_SLCP_Number": top_candidate.get("number", ""),
                        "Top_SLCP_Section": top_candidate.get("section", ""),
                        "Top_SLCP_Question": top_candidate.get("question", ""),
                        "Score": score,
                        "Score_Type": score_type,
                        "Reranked": mapping.get("reranked", False),
                        "Claude_Reason": top_candidate.get("reason", "") if mapping.get("reranked") else "",
                    })

            if df_data:
                df = pd.DataFrame(df_data)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="rsc_slcp_mappings.csv",
                    mime="text/csv",
                )
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_section = st.multiselect(
            "Filter by Section",
            options=sorted(set(m.get("section", "") for m in mappings.values())),
            default=None,
        )

    with col2:
        filter_reranked = st.selectbox(
            "Filter by Status",
            options=["All", "Hybrid Only", "Reranked with Claude"],
            index=0,
        )

    with col3:
        min_score = st.slider(
            "Minimum Top Score",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.05,
        )

    st.divider()

    # Display mappings
    filtered_mappings = {}
    for k, v in mappings.items():
        # Skip if error
        if "error" in v:
            filtered_mappings[k] = v
            continue

        # Get top candidate score (handle both old and new format)
        top_score = 0
        if v.get("candidates"):
            top_cand = v["candidates"][0]

            # Check if candidate is a dict (new format) or string (old cached format)
            if isinstance(top_cand, dict):
                if v.get("reranked"):
                    top_score = top_cand.get("llm_score", 0)
                else:
                    top_score = top_cand.get("embedding_score", 0)
            else:
                # Old format (string) - skip score filtering
                top_score = min_score  # Set to min to always pass filter

        # Apply filters
        section_match = not filter_section or v.get("section", "") in filter_section
        score_match = top_score >= min_score

        # Reranked filter
        if filter_reranked == "Hybrid Only":
            reranked_match = not v.get("reranked", False)
        elif filter_reranked == "Reranked with Claude":
            reranked_match = v.get("reranked", False)
        else:  # "All"
            reranked_match = True

        if section_match and score_match and reranked_match:
            filtered_mappings[k] = v
    
    if not filtered_mappings:
        st.info("No mappings match the selected filters.")
    else:
        st.info(f"Showing {len(filtered_mappings)} of {len(mappings)} mappings")
        
        for key, mapping in filtered_mappings.items():
            render_mapping_result(mapping, 0, key)


# ============================================================================
# MAIN APP
# ============================================================================


def main() -> None:
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Mapper Copilot - Batch RSC to SLCP",
        page_icon="🔄",
        layout="wide",
    )
    
    st.title("🔄 Mapper Copilot - RSC to SLCP Question Mapping")
    st.markdown(
        "**Automatic mapping of all RSC questions to SLCP equivalents using "
        "two-stage semantic search + LLM ranking.**"
    )
    
    st.divider()
    
    # Load data
    with st.spinner("Loading RSC questions..."):
        rsc_questions = load_rsc_questions()
    
    with st.spinner("Loading SLCP data dictionary..."):
        slcp_questions = load_slcp_questions()
    
    if not rsc_questions or not slcp_questions:
        st.error("Failed to load data files.")
        return
    
    # Check cache
    rsc_hash = get_cache_hash(rsc_questions)
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
            f"⏱️ Ready to map {len(rsc_questions)} RSC questions to "
            f"{len(slcp_questions)} SLCP questions"
        )
        
        if st.button("🚀 Start Mapping All Questions", key="start_mapping", use_container_width=True):
            with st.spinner("Building suggester..."):
                suggester = build_suggester(slcp_questions)
            
            # Create progress indicators
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Map all questions
            with st.spinner("Mapping questions..."):
                mappings = map_all_rsc_questions(
                    rsc_questions,
                    suggester,
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
        render_all_mappings_section(st.session_state.mappings)
        
        # Reset option
        st.divider()
        if st.button("🔄 Clear Cache & Remap", use_container_width=True):
            get_cache_file().unlink(missing_ok=True)
            st.session_state.mappings = None
            st.rerun()


if __name__ == "__main__":
    main()
