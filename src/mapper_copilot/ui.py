"""Streamlit interface for interactive RSC to SLCP question mapping."""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from mapper_copilot.core.suggester import Suggester
from mapper_copilot.models import Mapping
from mapper_copilot.providers.embeddings import HashingEmbedder
from mapper_copilot.providers.llm import MockLLM
from mapper_copilot.providers.vector_store import NumpyVectorStore

PAGE_TITLE = "Mapper Copilot"
APP_TITLE = "Mapper Copilot - RSC to SLCP Question Mapper"
APP_SUBTITLE = "AI-powered mapping using two-stage RAG"
DEFAULT_TOP_K = 5
DEFAULT_SOURCE_CANDIDATES = [
    "Operating license/registration is available and up to date",
    "Worker contracts are maintained and signed",
    "Emergency exits are clearly marked and unobstructed",
    "Workers are paid accurately and on time",
    "Workers have access to a grievance mechanism",
]
RESULT_COLUMNS = ("rsc_question", "mapped_to", "confidence", "rule")


@st.cache_resource(show_spinner=False)
def build_suggester(top_k: int = DEFAULT_TOP_K) -> Suggester:
    """Create a cached suggester backed by deterministic offline providers."""

    embedder = HashingEmbedder()
    vector_store = NumpyVectorStore()
    vector_store.index(
        vectors=embedder.batch_embed(DEFAULT_SOURCE_CANDIDATES),
        metadata=[{"question": candidate} for candidate in DEFAULT_SOURCE_CANDIDATES],
    )
    return Suggester(
        embedding_provider=embedder,
        llm_provider=MockLLM(),
        vector_store=vector_store,
        top_k=top_k,
    )


def configure_page(streamlit_module: Any = st) -> None:
    """Configure the Streamlit page."""

    streamlit_module.set_page_config(page_title=PAGE_TITLE, layout="wide")


def ensure_suggester(top_k: int = DEFAULT_TOP_K, streamlit_module: Any = st) -> Suggester:
    """Ensure a suggester exists in session state for the current top-k setting."""

    if (
        "suggester" not in streamlit_module.session_state
        or streamlit_module.session_state.get("suggester_top_k") != top_k
    ):
        streamlit_module.session_state["suggester"] = build_suggester(top_k)
        streamlit_module.session_state["suggester_top_k"] = top_k
    return streamlit_module.session_state["suggester"]


def get_sidebar(streamlit_module: Any = st) -> Any:
    """Return the sidebar object when available."""

    return getattr(streamlit_module, "sidebar", streamlit_module)


def render_sidebar(streamlit_module: Any = st) -> int:
    """Render sidebar controls and provider information."""

    sidebar = get_sidebar(streamlit_module)
    sidebar.header("About this tool")
    sidebar.info("Interactive RSC→SLCP mapping with deterministic offline providers.")
    sidebar.write("Embeddings: Hashing")
    sidebar.write("LLM: Mock")
    sidebar.write("VectorStore: Numpy")
    top_k = sidebar.slider("Top candidates (top_k)", min_value=1, max_value=20, value=DEFAULT_TOP_K)

    candidates = streamlit_module.session_state.get("last_candidates", [])
    if candidates:
        sidebar.subheader("Top candidates")
        for index, candidate in enumerate(candidates, start=1):
            sidebar.write(f"{index}. {candidate}")
    return int(top_k)


def render_header(streamlit_module: Any = st) -> None:
    """Render the main page heading."""

    streamlit_module.title(APP_TITLE)
    streamlit_module.caption(APP_SUBTITLE)


def confidence_status(confidence: float) -> tuple[str, str]:
    """Return a semantic label and Streamlit status type for confidence."""

    if confidence > 0.7:
        return "High confidence match", "success"
    if confidence >= 0.4:
        return "Medium confidence match", "warning"
    return "Low confidence match", "error"


def show_mapping_result(mapping: Mapping, streamlit_module: Any = st) -> None:
    """Display a mapping result with confidence visualization."""

    streamlit_module.subheader("Mapping Result")
    left_column, right_column = streamlit_module.columns(2)
    left_column.write("**Mapped SLCP Question**")
    left_column.write(mapping.mapped_to or "No mapping found")
    right_column.metric("Confidence score", f"{mapping.confidence:.2f}")
    streamlit_module.progress(int(mapping.confidence * 100))

    message, status = confidence_status(mapping.confidence)
    getattr(streamlit_module, status)(message)
    streamlit_module.write(f"**Mapping Rule:** {mapping.rule or 'No mapping rule available.'}")


def handle_single_mapping(question: str, suggester: Suggester, streamlit_module: Any = st) -> None:
    """Generate and store a mapping for a single question."""

    cleaned_question = question.strip()
    if not cleaned_question:
        streamlit_module.error("Please enter an RSC question before searching.")
        return

    try:
        mapping = suggester.suggest(cleaned_question)
    except Exception as exc:
        streamlit_module.error(f"Unable to generate a mapping right now: {exc}")
        return

    streamlit_module.session_state["single_mapping"] = mapping
    streamlit_module.session_state["last_candidates"] = mapping.source_candidates


def render_single_mapping_section(suggester: Suggester, streamlit_module: Any = st) -> None:
    """Render the interactive single-question mapping controls."""

    streamlit_module.subheader("Interactive Mapping")
    question = streamlit_module.text_input("Enter RSC Question")
    if streamlit_module.button("Find SLCP Mapping"):
        handle_single_mapping(question, suggester, streamlit_module)

    mapping = streamlit_module.session_state.get("single_mapping")
    if mapping is not None:
        show_mapping_result(mapping, streamlit_module)


def parse_uploaded_questions(uploaded_file: Any) -> list[str]:
    """Parse CSV content and return non-empty RSC questions."""

    raw_bytes = uploaded_file.getvalue()
    if not raw_bytes:
        return []

    try:
        import pandas as pd

        dataframe = pd.read_csv(io.BytesIO(raw_bytes))
        if "rsc_question" not in dataframe.columns:
            raise ValueError("CSV must include an 'rsc_question' column")
        return [
            str(value).strip() for value in dataframe["rsc_question"].tolist() if str(value).strip()
        ]
    except ImportError:
        text_stream = io.StringIO(raw_bytes.decode("utf-8-sig"))
        reader = csv.DictReader(text_stream)
        if not reader.fieldnames or "rsc_question" not in reader.fieldnames:
            raise ValueError("CSV must include an 'rsc_question' column")
        return [
            row["rsc_question"].strip() for row in reader if row.get("rsc_question", "").strip()
        ]


def mappings_to_rows(mappings: list[Mapping]) -> list[dict[str, Any]]:
    """Convert mapping objects to table rows."""

    return [
        {
            "rsc_question": mapping.rsc_question,
            "mapped_to": mapping.mapped_to,
            "confidence": round(mapping.confidence, 2),
            "rule": mapping.rule,
        }
        for mapping in mappings
    ]


def rows_to_csv(rows: list[dict[str, Any]]) -> bytes:
    """Serialize result rows to CSV bytes."""

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(RESULT_COLUMNS))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def show_batch_results(rows: list[dict[str, Any]], streamlit_module: Any = st) -> None:
    """Display batch results and a CSV download button."""

    try:
        import pandas as pd

        streamlit_module.dataframe(pd.DataFrame(rows), use_container_width=True)
    except ImportError:
        streamlit_module.dataframe(rows, use_container_width=True)

    streamlit_module.download_button(
        "Download results CSV",
        data=rows_to_csv(rows),
        file_name="mapper_copilot_results.csv",
        mime="text/csv",
    )


def render_batch_section(suggester: Suggester, streamlit_module: Any = st) -> None:
    """Render the batch CSV upload workflow."""

    streamlit_module.subheader("Batch Upload")
    uploaded_file = streamlit_module.file_uploader(
        "Upload CSV with rsc_question column", type=["csv"]
    )

    if streamlit_module.button("Process Batch"):
        if uploaded_file is None:
            streamlit_module.error("Upload a CSV file before processing a batch.")
        else:
            try:
                questions = parse_uploaded_questions(uploaded_file)
                if not questions:
                    raise ValueError("No valid RSC questions were found in the uploaded CSV")
                rows = mappings_to_rows(suggester.suggest_batch(questions))
                streamlit_module.session_state["batch_rows"] = rows
            except Exception as exc:
                streamlit_module.error(f"Unable to process the uploaded CSV: {exc}")

    rows = streamlit_module.session_state.get("batch_rows")
    if rows:
        show_batch_results(rows, streamlit_module)


def render_app(streamlit_module: Any = st) -> None:
    """Render the complete Streamlit application."""

    configure_page(streamlit_module)
    render_header(streamlit_module)
    top_k = render_sidebar(streamlit_module)
    suggester = ensure_suggester(top_k=top_k, streamlit_module=streamlit_module)
    render_single_mapping_section(suggester, streamlit_module)
    render_batch_section(suggester, streamlit_module)


if __name__ == "__main__":
    render_app()
