"""Simplified UI rendering using Streamlit native components."""
import streamlit as st


def render_result_card_simple(
    rank: int,
    slcp_key: str,
    number: str,
    section: str,
    question: str,
    score_pct: int,
    reason: str = "",
    is_top: bool = False,
) -> None:
    """Render a result card using Streamlit native components.

    Args:
        rank: Rank number (1-5)
        slcp_key: SLCP key (e.g., 'ms-6-1x')
        number: SLCP number (e.g., 'MS-CHE-1-1')
        section: SLCP section
        question: Question text (plain text, will not be escaped)
        score_pct: Score as percentage (0-100)
        reason: Optional reason text from Claude
        is_top: Whether this is the top result
    """
    # Colors based on rank
    border_color = "#99f6e4" if is_top else "#e5dfd6"
    border_width = "2px" if is_top else "1px"
    rank_color = "#0d9488" if is_top else "#a8a29e"
    key_bg = "#f0fdfa" if is_top else "#f2efea"
    key_border = "#99f6e4" if is_top else "#e5dfd6"

    # Score color
    if score_pct >= 65:
        score_color = "#0d9488"
    elif score_pct >= 45:
        score_color = "#d97706"
    else:
        score_color = "#a8a29e"

    # Escape question text to prevent HTML injection
    import html
    question_escaped = html.escape(question)
    reason_escaped = html.escape(reason) if reason else ""

    # Build card HTML - NO COMMENTS (they break Streamlit rendering)
    card_html = f"""<div style="border: {border_width} solid {border_color}; border-radius: 10px; padding: 16px 20px; margin-bottom: 12px; background: white; display: flex; align-items: flex-start;"><div style="font-family: monospace; font-size: 18px; color: {rank_color}; font-weight: bold; padding-top: 2px; margin-right: 16px; min-width: 28px;">{rank}</div><div style="flex: 1;"><div style="margin-bottom: 8px;"><code style="background: {key_bg}; border: 1px solid {key_border}; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-right: 8px;">{slcp_key}</code><code style="background: #fef3c7; border: 1px solid #fde047; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-right: 8px;">{number}</code><span style="font-size: 10px; font-weight: 600; color: #0d9488; letter-spacing: 0.06em; text-transform: uppercase;">{section}</span></div><div style="font-size: 14px; color: #1c1917; line-height: 1.5; margin-bottom: {8 if reason else 0}px;">{question_escaped}</div>{'<div style="font-size: 12px; color: #6b6560; font-style: italic; padding-left: 10px; border-left: 2px solid #e5dfd6;">' + reason_escaped + '</div>' if reason else ''}</div><div style="text-align: right; font-family: monospace; font-size: 15px; font-weight: 500; color: {score_color}; padding-top: 2px; margin-left: 16px; min-width: 50px;">{score_pct}%</div></div>"""

    st.markdown(card_html, unsafe_allow_html=True)
