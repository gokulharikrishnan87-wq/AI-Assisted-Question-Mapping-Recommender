"""Test HTML rendering in Streamlit."""
import streamlit as st

st.set_page_config(page_title="HTML Rendering Test")

# Test 1: Simple HTML
st.markdown("### Test 1: Simple HTML")
simple_html = '<p style="color: red;">This should be red text</p>'
st.markdown(simple_html, unsafe_allow_html=True)

# Test 2: Complex nested HTML like render_result_card
st.markdown("### Test 2: Complex nested HTML")
complex_html = '''
<div style="background:#ffffff;border:1px solid #e5dfd6;
  border-radius:10px;padding:16px 20px;margin-bottom:8px;">
  <p style="font-size:13.5px;color:#1c1917;line-height:1.55;margin:0;">
    This is a test question text
  </p>
</div>
'''
st.markdown(complex_html, unsafe_allow_html=True)

# Test 3: What happens with escaped HTML
st.markdown("### Test 3: Escaped HTML (this will show tags)")
import html
escaped_text = html.escape('<p>This will show tags</p>')
st.markdown(f'<div>{escaped_text}</div>', unsafe_allow_html=True)

# Test 4: Direct text in markdown
st.markdown("### Test 4: The actual render_result_card output")
from src.mapper_copilot.ui_helpers_inline import render_result_card
card = render_result_card(
    rank=1,
    slcp_key="test-key",
    section="TEST SECTION",
    question="This is a test question",
    score_pct=75,
    rsc_section="TEST",
    tab_prefix="test",
    rank_index=0,
    is_top=True,
)
st.markdown(card, unsafe_allow_html=True)
