# ui/theme.py
"""Anthropic 品牌色极简主题。

只做配色与字体回退，不使用脆弱的 DOM hack。
Poppins / Lora 未随项目分发时，回退到系统无衬线/衬线字体及中文字体。
"""

import streamlit as st

_BRAND_CSS = """
<style>
:root {
    --brand-ink: #141413;
    --brand-bg: #faf9f5;
    --brand-surface: #e8e6dc;
    --brand-muted: #b0aea5;
    --brand-accent: #d97757;
}

.stApp {
    background-color: var(--brand-bg);
    color: var(--brand-ink);
}

h1, h2, h3, h4, h5 {
    font-family: "Poppins", Arial, "Microsoft YaHei", sans-serif;
    color: var(--brand-ink);
    letter-spacing: -0.01em;
}

p, label, li, span, div.stMarkdown, textarea, input, .stCaption {
    font-family: "Lora", Georgia, "Microsoft YaHei", serif;
}

[data-testid="stForm"] {
    border: 1px solid var(--brand-surface);
    border-radius: 8px;
    padding: 1.2rem 1.2rem 0.6rem;
    background-color: #ffffff;
}

.stButton > button,
.stDownloadButton > button,
.stFormSubmitButton > button {
    font-family: "Poppins", Arial, "Microsoft YaHei", sans-serif;
    border-radius: 6px;
}

hr {
    border-color: var(--brand-surface);
}
</style>
"""


def apply_theme() -> None:
    """注入品牌样式。须在 st.set_page_config 之后调用。"""
    st.markdown(_BRAND_CSS, unsafe_allow_html=True)
