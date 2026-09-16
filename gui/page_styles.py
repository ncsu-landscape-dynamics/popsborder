# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from __future__ import annotations

from html import escape

import streamlit as st


_SHARED_PAGE_STYLES = """
<style>
.stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
    font-size: 24px;
    font-weight: 700;
}

.stTabs [data-baseweb="tab-list"] button {
    padding: 18px 24px;
}

.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] [data-testid="stMarkdownContainer"] p {
    color: #1f77b4;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
}

.stSelectbox label,
.stNumberInput label,
.stTextInput label,
.stSlider label,
.stRadio label,
.stTextArea label,
.stFileUploader label,
.stMultiSelect label {
    font-size: 20px !important;
    font-weight: 600 !important;
    color: #1f77b4 !important;
}

.stSelectbox div[data-baseweb="select"] > div {
    font-size: 18px !important;
    color: #2c3e50 !important;
    font-weight: 500 !important;
}

.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    font-size: 18px !important;
    color: #2c3e50 !important;
    font-weight: 500 !important;
}

.stMultiSelect div[data-baseweb="select"] > div {
    font-size: 18px !important;
    color: #2c3e50 !important;
    font-weight: 500 !important;
}

.selectbox-with-tooltip {
    position: relative;
    display: inline-block;
}

.info-icon {
    display: inline-block;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background-color: #1f77b4;
    color: white;
    text-align: center;
    line-height: 20px;
    font-size: 14px;
    margin-left: 8px;
    cursor: help;
    position: relative;
    vertical-align: middle;
    bottom: 125%;
    left: -0.5%;
}

.info-icon .tooltip {
    visibility: hidden;
    line-height: 18px;
    width: 300px;
    background-color: #2c3e50;
    color: #fff;
    text-align: left;
    border-radius: 8px;
    padding: 15px;
    position: absolute;
    z-index: 999;
    bottom: 125%;
    left: 50%;
    margin-left: -150px;
    opacity: 0;
    transition: opacity 0.3s;
    font-size: 14px;
    font-weight: 400;
    box-shadow: 0 4px 6px rgba(0,0,0,0.2);
}

.info-icon .tooltip::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -6px;
    border-width: 6px;
    border-style: solid;
    border-color: #2c3e50 transparent transparent transparent;
}

.info-icon:hover .tooltip {
    visibility: visible;
    opacity: 1;
}

.number_and_slider_label {
    font-size: 20px;
    font-weight: 600;
    color: #1f77b4;
    margin-bottom: 8px;
}

.custom_label2 {
    font-size: 15px;
    font-weight: 600;
    color: #1f77b4;
    margin-bottom: 8px;
}

.help-icon {
    display: inline-block;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 2px solid #1f77b4;
    color: #1f77b4;
    text-align: center;
    line-height: 18px;
    font-size: 15px;
    font-weight: bold;
    margin-left: 8px;
    cursor: help;
    position: relative;
    vertical-align: middle;
}

.help-icon .helptext {
    visibility: hidden;
    width: 340px;
    background-color: #1f77b4;
    color: white;
    text-align: left;
    border-radius: 8px;
    padding: 15px;
    position: absolute;
    z-index: 999;
    bottom: 140%;
    left: 50%;
    margin-left: -170px;
    opacity: 0;
    transition: opacity 0.3s;
    font-size: 14px;
    font-weight: normal;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    line-height: 1.6;
}

.help-icon .helptext::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    margin-left: -8px;
    border-width: 8px;
    border-style: solid;
    border-color: #1f77b4 transparent transparent transparent;
}

.help-icon:hover .helptext {
    visibility: visible;
    opacity: 1;
}

.metric-container {
    border: 1px solid rgba(31, 119, 180, 0.18);
    border-radius: 10px;
    background: linear-gradient(180deg, rgba(31,119,180,0.05), rgba(31,119,180,0.02));
    padding: 14px 16px;
    min-height: 96px;
}

.metric-title {
    font-size: 20px;
    font-weight: 500;
    color: #1f77b4;
    margin: 0;
    line-height: 1.2;
}

.metric-value {
    font-size: 20px;
    font-weight: 500;
    color: #2c3e50;
    margin: 10px 0 0 0;
}
</style>
"""

_GLOSSARY_STYLES = """
<style>
.glossary-summary {
    border: 1px solid rgba(31, 119, 180, 0.18);
    border-radius: 14px;
    background: linear-gradient(180deg, rgba(31,119,180,0.06), rgba(31,119,180,0.02));
    padding: 16px 18px;
    margin-bottom: 18px;
}

.glossary-summary-title {
    font-size: 18px;
    font-weight: 700;
    color: #1f77b4;
    margin-bottom: 6px;
}

.glossary-summary-text {
    font-size: 16px;
    color: #2c3e50;
    line-height: 1.55;
}

.glossary-card {
    border: 1px solid rgba(31, 119, 180, 0.18);
    border-radius: 14px;
    background: #ffffff;
    padding: 16px 18px;
    margin-bottom: 16px;
    box-shadow: 0 6px 16px rgba(31, 119, 180, 0.06);
    min-height: 176px;
}

.glossary-badge {
    display: inline-block;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #1f77b4;
    background: rgba(31, 119, 180, 0.10);
    border: 1px solid rgba(31, 119, 180, 0.20);
    border-radius: 999px;
    padding: 4px 10px;
    margin-bottom: 12px;
}

.glossary-term {
    font-size: 20px;
    font-weight: 700;
    color: #1f77b4;
    margin: 0 0 10px 0;
    line-height: 1.25;
}

.glossary-definition {
    font-size: 16px;
    color: #2c3e50;
    line-height: 1.6;
    margin: 0;
}
</style>
"""


def apply_shared_page_styles() -> None:
    """Inject shared CSS styles for all Streamlit pages.

    This function applies common typography and component styles (tabs,
    labels, metrics, tooltips) using a single HTML/CSS block. Call this
    once at the top of each page script.
    """
    st.markdown(_SHARED_PAGE_STYLES, unsafe_allow_html=True)

def apply_glossary_page_styles() -> None:
    st.markdown(_GLOSSARY_STYLES, unsafe_allow_html=True)


def render_page_intro(description_html: str) -> None:
    """Render a formatted introductory text block for a page.

    Args:
        description_html: HTML string describing the page. It is inserted
            as-is inside a styled container, so it should be sanitized or
            trusted content.
    """
    st.markdown(
        f"""
        <div style='font-size: 18px; color: #2c3e50; line-height: 1;'>
            <p style='margin-bottom: 12px;'>
                {description_html}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(label: str, *, compact: bool = False) -> None:
    """Render a styled section header label.

    Args:
        label: Header text to display (escaped for HTML safety).
        compact: If True, use a smaller CSS style; otherwise use the
            default larger label style.
    """
    css_class = "custom_label2" if compact else "number_and_slider_label"
    st.markdown(
        f'<div class="{css_class}">{escape(label)}</div>',
        unsafe_allow_html=True,
    )


def render_labeled_help(label: str, help_text: str = "", *, compact: bool = False) -> None:
    """Render a label with an inline help tooltip icon.

    Args:
        label: Label text to display (escaped for HTML safety).
        help_text: Optional help/description text shown in a hover tooltip.
        compact: If True, use a smaller CSS style for the label.
    """
    css_class = "custom_label2" if compact else "number_and_slider_label"
    help_html = ""
    if help_text:
        help_html = (
            '<span class="help-icon">?'
            f'<span class="helptext">{escape(help_text)}</span>'
            "</span>"
        )
    st.markdown(
        f'<div class="{css_class}">{escape(label)}{help_html}</div>',
        unsafe_allow_html=True,
    )


def render_metric_card(title: str, value: str, help_text: str) -> None:
    """Render a metric card with a title, value, and help tooltip.

    The card is styled using the shared CSS, and includes a small "?"
    icon that shows the help text on hover.

    Args:
        title: Metric title or label.
        value: Metric value as a string.
        help_text: Help or description text shown in a tooltip when the
            info icon is hovered.
    """
    st.markdown(
        f"""
        <div class="metric-container">
            <p class="metric-title">
                {escape(title)}
                <span class="info-icon">
                    ?
                    <span class="tooltip">{escape(help_text)}</span>
                </span>
            </p>
            <p class="metric-value">{escape(value)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
