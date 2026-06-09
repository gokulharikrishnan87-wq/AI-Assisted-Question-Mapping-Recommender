"""Streamlit UI for Mapper Copilot - Testing with Local Embeddings and Real Data."""

import json
import os
from pathlib import Path
from typing import Any, List, Dict, Optional
import hashlib

import openpyxl
import pandas as pd
import streamlit as st

# Set environment for local embeddings BEFORE imports
os.environ['PROVIDER'] = 'local'
os.environ['EMBEDDING_MODEL_ID'] = 'all-MiniLM-L6-v2'
os.environ['EMBEDDING_DIMENSION'] = '384'

from mapper_copilot.core.suggester import Suggester
from mapper_copilot.providers.embeddings import create_embedding_provider_from_settings
from mapper_copilot.providers.llm import MockLLM
from mapper_copilot.providers.vector_store import NumpyVectorStore
from mapper_copilot.config import settings

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
    return CACHE_DIR / "rsc_mappings_cache_local.json"


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


def load_slcp_questions() -> Dict[str, str]:
    """Load SLCP questions from JSON."""
    if not os.path.exists(SLCP_DICT_FILE):
        st.error(f"SLCP data dictionary not found: {SLCP_DICT_FILE}")
        return {}

    with open(SLCP_DICT_FILE) as f:
        data = json.load(f)

    # Extract questions: {key: question_text}
    slcp_questions = {
        k: v.get("question", "")
        for k, v in data.items()
        if isinstance(v, dict) and "question" in v and v.get("question", "").strip()
    }

    return slcp_questions


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


def build_suggester(slcp_questions: Dict[str, str]) -> Suggester:
    """Build suggester with SLCP data and local embeddings."""
    embedder = create_embedding_provider_from_settings()
    llm = MockLLM()

    # Embed all SLCP questions first
    slcp_texts = list(slcp_questions.values())
    slcp_embeddings = embedder.batch_embed(slcp_texts)

    # Build metadata
    metadata_list = [
        {"slcp_question": question, "key": key}
        for key, question in slcp_questions.items()
    ]

    # Index embeddings (not text)
    vector_store = NumpyVectorStore()
    vector_store.index(slcp_embeddings, metadata_list)

    return Suggester(
        embedding_provider=embedder,
        llm_provider=llm,
        vector_store=vector_store,
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
    """Map all RSC questions to SLCP."""
    mappings = {}
    total = len(rsc_questions)

    for i, rsc_q in enumerate(rsc_questions):
        question_text = rsc_q.get("LLL Description", "")
        lll_key = rsc_q.get("LLL Key (unique)", f"RSC_{i}")

        if not question_text:
            continue

        try:
            result = suggester.suggest(question_text)

            # Extract top 5 candidates from source_candidates
            candidates = result.source_candidates[:5]

            mappings[lll_key] = {
                "rsc_question": question_text,
                "section": rsc_q.get("Section", ""),
                "best_match": result.mapped_to,
                "confidence": result.confidence,
                "rule": result.rule,
                "candidates": candidates,
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
    """Render a single mapping result with expandable details."""
    # Determine confidence color
    confidence = mapping.get("confidence", 0)

    if "error" in mapping:
        color = "🔴"
        status = "Error"
    elif confidence >= 0.7:
        color = "🟢"
        status = f"{confidence:.0%}"
    elif confidence >= 0.5:
        color = "🟡"
        status = f"{confidence:.0%}"
    else:
        color = "🔵"
        status = f"{confidence:.0%}"

    # Header with key and status
    col1, col2 = st.columns([0.1, 0.9])
    with col1:
        st.markdown(f"**{color}**")
    with col2:
        st.markdown(f"**{key}** — {mapping.get('section', '')}")

    # RSC Question (full text)
    st.markdown(f"**RSC Question:** {mapping['rsc_question']}")

    # Expandable details
    with st.expander(f"View mapping → {status}"):
        if "error" in mapping:
            st.error(f"Error: {mapping['error']}")
        else:
            # Best SLCP match (full text)
            st.markdown(f"### Best SLCP Match\n{mapping['best_match']}")
            st.markdown(f"**Confidence:** {mapping['confidence']:.1%}")
            st.markdown(f"**Mapping Rule:** {mapping['rule']}")

            # Top 5 candidates
            if mapping.get("candidates"):
                st.markdown("### Top 5 Alternative Candidates")
                for i, candidate in enumerate(mapping["candidates"], 1):
                    st.markdown(f"**{i}.** {candidate}")

    st.divider()


def render_all_mappings_section(mappings: Dict[str, Dict]) -> None:
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
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Export to CSV"):
            df_data = []
            for key, mapping in mappings.items():
                if "error" not in mapping:
                    df_data.append({
                        "RSC_Key": key,
                        "RSC_Question": mapping["rsc_question"],
                        "Section": mapping["section"],
                        "Best_SLCP_Match": mapping["best_match"],
                        "Confidence": mapping["confidence"],
                        "Mapping_Rule": mapping["rule"],
                    })

            if df_data:
                df = pd.DataFrame(df_data)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="rsc_slcp_mappings_local.csv",
                    mime="text/csv",
                )

    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        filter_section = st.multiselect(
            "Filter by Section",
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
            render_mapping_result(mapping, 0, key)


# ============================================================================
# MAIN APP
# ============================================================================


def main() -> None:
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Mapper Copilot - Local Embeddings Test",
        page_icon="🧠",
        layout="wide",
    )

    st.title("🧠 Mapper Copilot - RSC to SLCP Mapping (Local Embeddings)")
    st.markdown(
        "**Testing with local sentence-transformers - No AWS credentials needed!**"
    )

    # Show configuration
    with st.expander("⚙️ Configuration", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Provider", settings.provider)
        with col2:
            st.metric("Model", settings.embedding_model_id)
        with col3:
            st.metric("Dimensions", settings.embedding_dimension)

    st.divider()

    # Load data
    with st.spinner("Loading RSC questions..."):
        rsc_questions = load_rsc_questions()

    with st.spinner("Loading SLCP data dictionary..."):
        slcp_questions = load_slcp_questions()

    if not rsc_questions or not slcp_questions:
        st.error("Failed to load data files.")
        st.info("Make sure RSC Questions.xlsx and slcp_data_dictionary.json are in the current directory.")
        return

    st.success(f"✅ Loaded {len(rsc_questions)} RSC questions and {len(slcp_questions)} SLCP questions")

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
            f"{len(slcp_questions)} SLCP questions using **local semantic embeddings**"
        )

        st.info("💡 This will use the all-MiniLM-L6-v2 model for semantic understanding (no AWS needed)")

        if st.button("🚀 Start Mapping All Questions", key="start_mapping", use_container_width=True):
            with st.spinner("Building suggester with local embeddings..."):
                suggester = build_suggester(slcp_questions)

            st.success("✅ Local embedding model loaded!")

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
            st.success(f"✅ Mapping complete! {len(mappings)} questions processed using local embeddings.")
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
