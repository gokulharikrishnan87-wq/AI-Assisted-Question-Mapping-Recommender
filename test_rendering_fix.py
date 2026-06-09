"""Test the rendering fix."""
import sys
sys.path.insert(0, 'src')

import streamlit as st
from mapper_copilot.ui_simple_render import render_result_card_simple

st.set_page_config(page_title="Rendering Fix Test", layout="wide")

st.title("Test: Simplified Rendering")

st.markdown("### Test 1: Simple question text")
render_result_card_simple(
    rank=1,
    slcp_key="ms-6-1x",
    number="MS-CHE-1-1",
    section="MANAGEMENT SYSTEMS",
    question="Facility conducts regular internal reviews and/or assessments of all social and labor policies and procedures that the facility has implemented",
    score_pct=75,
    reason="",
    is_top=True,
)

st.markdown("### Test 2: With Claude reason")
render_result_card_simple(
    rank=2,
    slcp_key="wb-2--2",
    number="WB-WAGE-2",
    section="WAGES & BENEFITS",
    question="Does the facility maintain only one accurate payroll record?",
    score_pct=69,
    reason="This question directly relates to maintaining accurate payroll documents as mentioned in the RSC question.",
    is_top=False,
)

st.markdown("### Test 3: Low score")
render_result_card_simple(
    rank=3,
    slcp_key="wh-3",
    number="WH-WOR-3",
    section="WORKING HOURS",
    question="Does the facility maintain only one accurate set of working hour records?",
    score_pct=42,
    reason="",
    is_top=False,
)

st.success("✅ If you can see the question text properly above (not HTML tags), the fix is working!")
