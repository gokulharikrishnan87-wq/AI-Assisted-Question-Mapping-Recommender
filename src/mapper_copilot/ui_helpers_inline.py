"""UI helper functions with inline styles (no CSS variables)."""

import html
import streamlit as st


def inject_fonts() -> None:
    """Inject Google Fonts once per session."""
    if st.session_state.get("_fonts_loaded"):
        return

    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;1,9..40,400&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_fonts_loaded"] = True


def inject_css() -> None:
    """Inject CSS for tabs and buttons."""
    if st.session_state.get("_css_loaded"):
        return

    st.markdown(
        """
        <style>
        /* Tab bar styling */
        div[data-testid="stTabs"] > div:first-child {
          border-bottom: 1px solid #e5dfd6;
          gap: 0;
        }
        div[data-testid="stTabs"] button[role="tab"] {
          font-family: 'DM Sans', sans-serif;
          font-size: 13px;
          font-weight: 500;
          color: #a8a29e;
          background: none;
          border: none;
          border-bottom: 2px solid transparent;
          padding: 10px 18px 10px 0;
          transition: color 0.15s, border-color 0.15s;
        }
        div[data-testid="stTabs"] button[role="tab"]:hover {
          color: #6b6560;
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
          color: #0d9488;
          border-bottom-color: #0d9488;
        }

        /* Button styling */
        .stButton > button {
          font-family: 'DM Sans', sans-serif;
          font-size: 13px;
          font-weight: 500;
          color: #0d9488 !important;
          background: #f0fdfa !important;
          border: 1px solid #99f6e4 !important;
          border-radius: 6px !important;
          padding: 9px 18px !important;
          transition: background 0.15s;
        }
        .stButton > button:hover {
          background: #ccfbf1 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_css_loaded"] = True


def render_rsc_card(rsc_question: str) -> None:
    """Render the RSC source question card above tabs."""
    rsc_question = html.escape(rsc_question)
    st.markdown(
        f"""
        <div style="background:#ffffff;border:1px solid #e5dfd6;
          border-radius:10px;padding:18px 22px;margin-bottom:16px;
          font-family:'DM Sans',sans-serif;">
          <p style="font-size:10px;font-weight:500;letter-spacing:0.09em;
            text-transform:uppercase;color:#a8a29e;margin:0 0 7px;">
            RSC question</p>
          <p style="font-size:15px;font-weight:500;color:#1c1917;
            line-height:1.5;margin:0;">{rsc_question}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result_card(
    rank: int,
    slcp_key: str,
    section: str,
    question: str,
    score_pct: int,
    rsc_section: str,
    tab_prefix: str,
    rank_index: int,
    reason: str | None = None,
    is_top: bool = False,
    number: str = "",
    parent_question: str = "",
) -> str:
    """Render result card with inline styles (no CSS variables).

    Args:
        parent_question: Parent question text (e.g., for MS-PLA-16-9, this would be the MS-PLA-16 question)
    """

    # HTML escape text content to prevent rendering issues
    question = html.escape(question)
    parent_question = html.escape(parent_question) if parent_question else ""
    slcp_key = html.escape(slcp_key)
    section = html.escape(section)
    number = html.escape(number) if number else ""

    # Border style
    border_style = "2px solid #99f6e4" if is_top else "1px solid #e5dfd6"

    # Rank color
    rank_color = "#0d9488" if is_top else "#a8a29e"

    # Key tag colors
    key_bg = "#f0fdfa" if is_top else "#f2efea"
    key_border = "#99f6e4" if is_top else "#e5dfd6"

    # Section color
    section_color = "#0d9488" if section == rsc_section else "#a8a29e"

    # Score colors
    if score_pct >= 65:
        score_color = "#0d9488"
        bar_color = "#0d9488"
    elif 45 <= score_pct < 65:
        score_color = "#d97706"
        bar_color = "#d97706"
    else:
        score_color = "#a8a29e"
        bar_color = "#ccc5bc"

    # Reason block
    if reason:
        reason = html.escape(reason)
        reason_html = f"""<p style="font-size:12px;color:#6b6560;font-style:italic;
          line-height:1.55;margin:9px 0 0;padding-left:10px;
          border-left:2px solid #e5dfd6;border-radius:0;">{reason}</p>"""
        reason_margin = "9px"
    else:
        reason_html = ""
        reason_margin = "0"

    # Unique bar ID and delay
    bar_id = f"{tab_prefix}-{slcp_key.replace(' ', '-')}"
    delay = rank_index * 70

    # Number badge (build separately to avoid f-string escaping issues)
    number_badge = ""
    if number:
        number_badge = f'<code style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;background:#fef3c7;border:1px solid #fde047;border-radius:4px;padding:1px 6px;color:#854d0e;">{number}</code>'

    # Parent question (if available)
    parent_html = ""
    if parent_question:
        parent_html = f'<p style="font-size:12px;color:#78716c;font-style:italic;line-height:1.5;margin:0 0 6px;padding-left:12px;border-left:3px solid #d6d3d1;">↳ {parent_question}</p>'

    return f"""
<div style="background:#ffffff;border:{border_style};
  border-radius:10px;padding:16px 20px;margin-bottom:8px;
  display:grid;grid-template-columns:28px 1fr 72px;gap:0 16px;
  align-items:start;font-family:'DM Sans',sans-serif;">

  <div style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:400;
    color:{rank_color};line-height:1;padding-top:3px;">{rank}</div>

  <div>
    <div style="display:flex;align-items:center;gap:10px;
      margin-bottom:7px;flex-wrap:wrap;">
      <code style="font-family:'IBM Plex Mono',monospace;font-size:12px;
        background:{key_bg};border:1px solid {key_border};
        border-radius:4px;padding:1px 8px;
        color:#1c1917;">{slcp_key}</code>
      {number_badge}
      <span style="font-size:10px;font-weight:600;letter-spacing:0.06em;
        text-transform:uppercase;color:{section_color};">{section}</span>
    </div>
    {parent_html}
    <p style="font-size:13.5px;color:#1c1917;line-height:1.55;margin:0 0 {reason_margin};">{question}</p>
    {reason_html}
  </div>

  <div style="display:flex;flex-direction:column;align-items:flex-end;
    gap:6px;padding-top:2px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:15px;font-weight:500;
      color:{score_color};">{score_pct}%</span>
    <div style="width:56px;height:3px;background:#e5dfd6;
      border-radius:2px;overflow:hidden;">
      <div id="{bar_id}" style="height:100%;border-radius:2px;width:0;
        background:{bar_color};
        transition:width 0.55s cubic-bezier(.4,0,.2,1);"></div>
    </div>
  </div>
</div>
<script>
  setTimeout(() => {{
    const b = document.getElementById('{bar_id}');
    if (b) b.style.width = '{score_pct}%';
  }}, {delay});
</script>
"""


def render_empty_rerank_state() -> None:
    """Render the empty state for Claude rerank tab."""
    st.markdown(
        """
        <div style="background:#ffffff;border:1px solid #e5dfd6;
          border-radius:10px;padding:28px 24px;margin-bottom:16px;
          font-family:'DM Sans',sans-serif;">
          <p style="font-size:13px;color:#6b6560;line-height:1.5;margin:0 0 14px;">
            Reranks the 5 semantic candidates using Claude's reasoning.<br>
            Results include a relevance score and a short explanation per match.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_rerank_disabled_hint() -> None:
    """Render hint when reranker is not configured."""
    st.markdown(
        """
        <p style="font-size:12px;color:#a8a29e;font-family:'DM Sans',sans-serif;
          padding:8px 0;">
          Set <code style="font-family:'IBM Plex Mono',monospace;">RERANKER=llm</code> and
          <code style="font-family:'IBM Plex Mono',monospace;">ANTHROPIC_API_KEY</code> in
          <code style="font-family:'IBM Plex Mono',monospace;">.env</code> to enable this tab.
        </p>
        """,
        unsafe_allow_html=True,
    )


def render_reranked_header(model_name: str) -> None:
    """Render header for reranked results section."""
    # Strip 'claude-' prefix and capitalize
    if model_name.startswith("claude-"):
        model_label = model_name[7:].replace("-", " ").title()
    else:
        model_label = model_name.title()

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;
          font-family:'DM Sans',sans-serif;">
          <span style="font-size:10px;font-weight:600;letter-spacing:0.09em;
            text-transform:uppercase;color:#6b6560;">Reranked results</span>
          <span style="font-size:11px;color:#a8a29e;">{model_label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
