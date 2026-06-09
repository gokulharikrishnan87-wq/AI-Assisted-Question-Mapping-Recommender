"""UI helper functions for Streamlit interface."""

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
    """Inject CSS variables and component styles once per session."""
    if st.session_state.get("_css_loaded"):
        return

    st.markdown(
        """
        <style>
        :root {
          --surface:        #ffffff;
          --surface-muted:  #f2efea;
          --border:         #e5dfd6;
          --border-strong:  #ccc5bc;
          --text-1:         #1c1917;
          --text-2:         #6b6560;
          --text-3:         #a8a29e;
          --success:        #0d9488;
          --success-bg:     #f0fdfa;
          --success-border: #99f6e4;
          --warning:        #d97706;
          --radius:         10px;
          --radius-sm:      6px;
          --sans:           'DM Sans', sans-serif;
          --mono:           'IBM Plex Mono', monospace;
        }

        /* Tab bar styling */
        div[data-testid="stTabs"] > div:first-child {
          border-bottom: 1px solid var(--border);
          gap: 0;
        }
        div[data-testid="stTabs"] button[role="tab"] {
          font-family: var(--sans);
          font-size: 13px;
          font-weight: 500;
          color: var(--text-3);
          background: none;
          border: none;
          border-bottom: 2px solid transparent;
          padding: 10px 18px 10px 0;
          transition: color 0.15s, border-color 0.15s;
        }
        div[data-testid="stTabs"] button[role="tab"]:hover {
          color: var(--text-2);
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
          color: var(--success);
          border-bottom-color: var(--success);
        }

        /* Button styling */
        .stButton > button {
          font-family: var(--sans);
          font-size: 13px;
          font-weight: 500;
          color: var(--success) !important;
          background: var(--success-bg) !important;
          border: 1px solid var(--success-border) !important;
          border-radius: var(--radius-sm) !important;
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
    st.markdown(
        f"""
        <div style="background:var(--surface);border:1px solid var(--border);
          border-radius:var(--radius);padding:18px 22px;margin-bottom:16px;
          font-family:var(--sans);">
          <p style="font-size:10px;font-weight:500;letter-spacing:0.09em;
            text-transform:uppercase;color:var(--text-3);margin:0 0 7px;">
            RSC question</p>
          <p style="font-size:15px;font-weight:500;color:var(--text-1);
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
) -> str:
    """
    Render a single SLCP result card with animated score bar.

    Args:
        rank: Display rank (1-5)
        slcp_key: SLCP key identifier
        section: SLCP section name
        question: SLCP question text
        score_pct: Score as percentage (0-100)
        rsc_section: RSC section for cross-highlighting
        tab_prefix: "sem" or "llm" for unique bar IDs
        rank_index: 0-based index for stagger delay
        reason: Optional explanation text (LLM reranker)
        is_top: Whether this is rank 1 (special styling)

    Returns:
        HTML string for the card
    """
    # Border style
    border_style = "2px solid var(--success-border)" if is_top else "1px solid var(--border)"

    # Rank color
    rank_color = "var(--success)" if is_top else "var(--text-3)"

    # Key tag colors
    key_bg = "var(--success-bg)" if is_top else "var(--surface-muted)"
    key_border = "var(--success-border)" if is_top else "var(--border)"

    # Section color (highlight if matches RSC section)
    section_color = "var(--success)" if section == rsc_section else "var(--text-3)"

    # Score colors based on percentage
    if score_pct >= 65:
        score_color = "var(--success)"
        bar_color = "var(--success)"
    elif 45 <= score_pct < 65:
        score_color = "var(--warning)"
        bar_color = "var(--warning)"
    else:
        score_color = "var(--text-3)"
        bar_color = "var(--border-strong)"

    # Reason block
    if reason:
        reason_html = f"""<p style="font-size:12px;color:var(--text-2);font-style:italic;
          line-height:1.55;margin:9px 0 0;padding-left:10px;
          border-left:2px solid var(--border);border-radius:0;">{reason}</p>"""
        reason_margin = "9px"
    else:
        reason_html = ""
        reason_margin = "0"

    # Unique bar ID and delay
    bar_id = f"{tab_prefix}-{slcp_key.replace(' ', '-')}"
    delay = rank_index * 70

    return f"""
<div style="background:var(--surface);border:{border_style};
  border-radius:var(--radius);padding:16px 20px;margin-bottom:8px;
  display:grid;grid-template-columns:28px 1fr 72px;gap:0 16px;
  align-items:start;font-family:var(--sans);">

  <div style="font-family:var(--mono);font-size:18px;font-weight:400;
    color:{rank_color};line-height:1;padding-top:3px;">{rank}</div>

  <div>
    <div style="display:flex;align-items:center;gap:10px;
      margin-bottom:7px;flex-wrap:wrap;">
      <code style="font-family:var(--mono);font-size:12px;
        background:{key_bg};border:1px solid {key_border};
        border-radius:4px;padding:1px 8px;
        color:var(--text-1);">{slcp_key}</code>
      <span style="font-size:10px;font-weight:600;letter-spacing:0.06em;
        text-transform:uppercase;color:{section_color};">{section}</span>
    </div>
    <p style="font-size:13.5px;color:var(--text-1);line-height:1.55;
      margin:0 0 {reason_margin};">{question}</p>
    {reason_html}
  </div>

  <div style="display:flex;flex-direction:column;align-items:flex-end;
    gap:6px;padding-top:2px;">
    <span style="font-family:var(--mono);font-size:15px;font-weight:500;
      color:{score_color};">{score_pct}%</span>
    <div style="width:56px;height:3px;background:var(--border);
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
        <div style="background:var(--surface);border:1px solid var(--border);
          border-radius:var(--radius);padding:28px 24px;margin-bottom:16px;
          font-family:var(--sans);">
          <p style="font-size:13px;color:var(--text-2);line-height:1.5;margin:0 0 14px;">
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
        <p style="font-size:12px;color:var(--text-3);font-family:var(--sans);
          padding:8px 0;">
          Set <code style="font-family:var(--mono);">RERANKER=llm</code> and
          <code style="font-family:var(--mono);">ANTHROPIC_API_KEY</code> in
          <code style="font-family:var(--mono);">.env</code> to enable this tab.
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
          font-family:var(--sans);">
          <span style="font-size:10px;font-weight:600;letter-spacing:0.09em;
            text-transform:uppercase;color:var(--text-2);">Reranked results</span>
          <span style="font-size:11px;color:var(--text-3);">{model_label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
