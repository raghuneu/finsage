"""FinSage UI theme — Midnight Teal palette aligned with PDF report branding."""

import streamlit as st

THEME = {
    "dark": "#0f172a",
    "accent": "#0ea5e9",
    "accent_light": "#e0f2fe",
    "bullish": "#06d6a0",
    "bearish": "#ef476f",
    "neutral": "#94a3b8",
    "bg": "#ffffff",
    "card_bg": "#f8fafc",
    "border": "#e2e8f0",
    "text": "#0f172a",
    "text_muted": "#64748b",
    "light_gray": "#f1f5f9",
}


def inject_css():
    st.markdown("""<style>
    /* ─── Sidebar ─── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stRadio label {
        color: #94a3b8 !important;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="stSidebar"] hr {
        border-color: #334155;
    }

    /* ─── Cards ─── */
    .fs-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 12px;
    }
    .fs-card-accent {
        border-left: 4px solid #0ea5e9;
    }
    .fs-card h4 {
        color: #64748b;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .fs-card .value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 2px;
    }
    .fs-card .delta-up { color: #06d6a0; font-size: 0.85rem; font-weight: 600; }
    .fs-card .delta-down { color: #ef476f; font-size: 0.85rem; font-weight: 600; }

    /* ─── Signals ─── */
    .signal-bullish {
        background: #ecfdf5; color: #06d6a0; font-weight: 700;
        padding: 4px 14px; border-radius: 999px; font-size: 0.85rem;
        display: inline-block;
    }
    .signal-bearish {
        background: #fef2f2; color: #ef476f; font-weight: 700;
        padding: 4px 14px; border-radius: 999px; font-size: 0.85rem;
        display: inline-block;
    }
    .signal-neutral {
        background: #f1f5f9; color: #64748b; font-weight: 700;
        padding: 4px 14px; border-radius: 999px; font-size: 0.85rem;
        display: inline-block;
    }

    /* ─── Section headers ─── */
    .fs-section {
        border-left: 4px solid #0ea5e9;
        padding-left: 16px;
        margin: 24px 0 16px 0;
    }
    .fs-section h3 {
        color: #0f172a; font-size: 1.2rem; font-weight: 600; margin-bottom: 2px;
    }
    .fs-section p {
        color: #64748b; font-size: 0.85rem; margin: 0;
    }

    /* ─── Data source cards ─── */
    .ds-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
        color: white; padding: 16px 20px; border-radius: 12px;
        text-align: center;
    }
    .ds-card .icon { font-size: 1.8rem; margin-bottom: 4px; }
    .ds-card .name { font-weight: 700; font-size: 0.95rem; }
    .ds-card .sub { font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }

    /* ─── Status indicators ─── */
    .status-ok { color: #06d6a0; }
    .status-err { color: #ef476f; }
    .status-dot {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        margin-right: 6px; vertical-align: middle;
    }
    .status-dot.green { background: #06d6a0; }
    .status-dot.red { background: #ef476f; }
    .status-dot.amber { background: #f59e0b; }

    /* ─── Citations ─── */
    .citation-box {
        background: #f0f4f8; border-left: 4px solid #0ea5e9;
        padding: 10px 16px; margin: 6px 0; border-radius: 0 8px 8px 0;
        font-size: 0.85rem;
    }

    /* ─── Consensus ─── */
    .consensus-box {
        background: #f0fdf4; border: 2px solid #06d6a0;
        border-radius: 12px; padding: 20px; margin: 12px 0;
    }

    /* ─── Guardrail results ─── */
    .guardrail-pass {
        background: #f0fdf4; border: 1px solid #bbf7d0;
        padding: 16px; border-radius: 10px;
    }
    .guardrail-fail {
        background: #fef2f2; border: 1px solid #fecaca;
        padding: 16px; border-radius: 10px;
    }

    /* ─── Page title ─── */
    .fs-title {
        font-size: 2rem; font-weight: 700; color: #0f172a;
        margin-bottom: 0; line-height: 1.2;
    }
    .fs-subtitle {
        font-size: 1rem; color: #64748b; margin-top: 2px; margin-bottom: 20px;
    }

    /* ─── Tables ─── */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* ─── Divider ─── */
    .fs-divider {
        border: none; border-top: 1px solid #e2e8f0;
        margin: 20px 0;
    }
    </style>""", unsafe_allow_html=True)
