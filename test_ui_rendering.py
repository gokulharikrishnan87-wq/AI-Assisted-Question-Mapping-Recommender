"""Test if styled cards render properly in Streamlit."""

import streamlit as st
import sys
sys.path.insert(0, 'src')

from mapper_copilot.ui_helpers import (
    inject_fonts,
    inject_css,
    render_rsc_card,
    render_result_card,
)

st.set_page_config(page_title="UI Rendering Test", layout="wide")

# Inject fonts and CSS
inject_fonts()
inject_css()

st.title("🧪 UI Rendering Test")

st.header("1. RSC Card Test")
render_rsc_card("This is a test RSC question to verify card styling works correctly.")

st.header("2. Result Card Test (Top Rank)")
card_html = render_result_card(
    rank=1,
    slcp_key="ms-6-3x",
    section="MANAGEMENT SYSTEMS",
    question="Facility keeps records of these assessments and any violations that were uncovered",
    score_pct=85,
    rsc_section="1. Business Ethics",
    tab_prefix="test",
    rank_index=0,
    reason=None,
    is_top=True
)
st.markdown(card_html, unsafe_allow_html=True)

st.header("3. Result Card with Reason")
card_html2 = render_result_card(
    rank=2,
    slcp_key="fp-bi-20",
    section="FACILITY PROFILE",
    question="Facility Contact Name(s) of who is submitting the self/ or joint-assessment:",
    score_pct=50,
    rsc_section="1. Business Ethics",
    tab_prefix="test",
    rank_index=1,
    reason="This question relates to facility contact information which is relevant for access verification.",
    is_top=False
)
st.markdown(card_html2, unsafe_allow_html=True)

st.header("4. Tabs Test")
tab1, tab2 = st.tabs(["Test Tab 1", "Test Tab 2"])

with tab1:
    st.write("Tab 1 content")
    card_html3 = render_result_card(
        rank=1,
        slcp_key="test-1",
        section="TEST SECTION",
        question="Test question inside a tab",
        score_pct=75,
        rsc_section="Test",
        tab_prefix="tab1",
        rank_index=0,
        reason=None,
        is_top=True
    )
    st.markdown(card_html3, unsafe_allow_html=True)

with tab2:
    st.write("Tab 2 content")

st.success("✅ If you see styled cards above with borders, colors, and animated bars, the rendering works!")
st.info("If you see plain HTML text, there's a rendering issue.")
