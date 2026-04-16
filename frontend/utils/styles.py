"""FinSage UI theme — Enterprise dark theme with Bloomberg Terminal aesthetic."""

import streamlit as st

THEME = {
    # Backgrounds
    "bg": "#0a0e17",
    "bg_surface": "#111827",
    "bg_elevated": "#1a2332",
    "bg_sidebar": "#060a10",
    # Accent
    "accent": "#00d4ff",
    "accent_dim": "#0ea5e9",
    "accent_glow": "rgba(0,212,255,0.15)",
    # Semantic
    "bullish": "#00ff88",
    "bullish_dim": "#065f46",
    "bearish": "#ff3366",
    "bearish_dim": "#4c0519",
    "warning": "#ffaa00",
    "neutral": "#6b7280",
    # Text
    "text": "#e5e7eb",
    "text_bright": "#f9fafb",
    "text_muted": "#6b7280",
    "text_dim": "#4b5563",
    # Borders
    "border": "#1f2937",
    "border_accent": "rgba(0,212,255,0.2)",
}


def create_plotly_template():
    """Return a Plotly layout dict for consistent dark-themed charts."""
    return dict(
        paper_bgcolor="#0a0e17",
        plot_bgcolor="#111827",
        font=dict(color="#e5e7eb", family="Inter, system-ui, sans-serif", size=12),
        xaxis=dict(
            gridcolor="#1f2937",
            linecolor="#1f2937",
            zerolinecolor="#1f2937",
            tickfont=dict(color="#6b7280"),
        ),
        yaxis=dict(
            gridcolor="#1f2937",
            linecolor="#1f2937",
            zerolinecolor="#1f2937",
            tickfont=dict(color="#6b7280"),
        ),
        hoverlabel=dict(
            bgcolor="#1a2332",
            font_color="#e5e7eb",
            bordercolor="#00d4ff",
            font_size=12,
        ),
        colorway=["#00d4ff", "#00ff88", "#ff3366", "#ffaa00", "#a78bfa", "#f472b6", "#38bdf8", "#34d399"],
        margin=dict(l=40, r=20, t=50, b=40),
    )


def inject_css():
    st.markdown(
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        unsafe_allow_html=True,
    )
    st.markdown("""<style>
    /* ─── Global ─── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp {
        background: #0a0e17;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    .stApp *:not([class*="material"]):not([data-testid="stIconMaterial"]) {
        font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    }
    .stApp code, .stApp pre {
        font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    }
    /* Preserve Streamlit's icon fonts */
    .material-symbols-rounded,
    .material-symbols-outlined,
    .material-icons,
    [class*="material-symbols"],
    [data-testid="stIconMaterial"] span {
        font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    }
    .stApp > header { background: transparent !important; }

    /* Custom scrollbar */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0a0e17; }
    ::-webkit-scrollbar-thumb { background: #1f2937; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #374151; }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* ─── Sidebar ─── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #060a10 0%, #0a0e17 100%);
        border-right: 1px solid #1f2937;
    }
    [data-testid="stSidebar"]::before {
        content: '';
        display: block;
        height: 2px;
        background: linear-gradient(90deg, #00d4ff 0%, transparent 100%);
    }
    [data-testid="stSidebar"] * {
        color: #e5e7eb !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stRadio label {
        color: #6b7280 !important;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
    }
    [data-testid="stSidebar"] hr {
        border-color: #1f2937;
    }

    /* ─── Cards ─── */
    .fs-card {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 10px;
        padding: 20px 24px;
        margin-bottom: 12px;
        transition: border-color 0.2s ease;
    }
    .fs-card:hover {
        border-color: rgba(0,212,255,0.3);
    }
    .fs-card-accent {
        border-left: 3px solid #00d4ff;
    }
    .fs-card h4 {
        color: #6b7280;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 6px;
    }
    .fs-card .value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f9fafb;
        margin-bottom: 2px;
        line-height: 1.2;
    }
    .fs-card .delta-up { color: #00ff88; font-size: 0.85rem; font-weight: 600; }
    .fs-card .delta-down { color: #ff3366; font-size: 0.85rem; font-weight: 600; }

    /* ─── Signals ─── */
    .signal-bullish {
        background: rgba(0,255,136,0.1); color: #00ff88; font-weight: 700;
        padding: 4px 14px; border-radius: 999px; font-size: 0.85rem;
        display: inline-block; border: 1px solid rgba(0,255,136,0.2);
    }
    .signal-bearish {
        background: rgba(255,51,102,0.1); color: #ff3366; font-weight: 700;
        padding: 4px 14px; border-radius: 999px; font-size: 0.85rem;
        display: inline-block; border: 1px solid rgba(255,51,102,0.2);
    }
    .signal-neutral {
        background: rgba(107,114,128,0.1); color: #9ca3af; font-weight: 700;
        padding: 4px 14px; border-radius: 999px; font-size: 0.85rem;
        display: inline-block; border: 1px solid rgba(107,114,128,0.2);
    }

    /* ─── Section headers ─── */
    .fs-section {
        border-left: 3px solid #00d4ff;
        padding-left: 16px;
        margin: 28px 0 16px 0;
    }
    .fs-section h3 {
        color: #f9fafb; font-size: 1.15rem; font-weight: 600; margin-bottom: 2px;
    }
    .fs-section p {
        color: #6b7280; font-size: 0.85rem; margin: 0;
    }

    /* ─── Data source cards ─── */
    .ds-card {
        background: linear-gradient(135deg, #111827 0%, #1a2332 100%);
        border: 1px solid #1f2937;
        color: #e5e7eb; padding: 16px 20px; border-radius: 10px;
        text-align: center;
    }
    .ds-card:hover { border-color: rgba(0,212,255,0.3); }
    .ds-card .icon { font-size: 1.8rem; margin-bottom: 4px; }
    .ds-card .name { font-weight: 700; font-size: 0.95rem; color: #f9fafb; }
    .ds-card .sub { font-size: 0.75rem; color: #6b7280; margin-top: 2px; }

    /* ─── Status indicators ─── */
    .status-ok { color: #00ff88; }
    .status-err { color: #ff3366; }
    .status-dot {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        margin-right: 6px; vertical-align: middle;
    }
    .status-dot.green { background: #00ff88; box-shadow: 0 0 6px rgba(0,255,136,0.4); }
    .status-dot.red { background: #ff3366; }
    .status-dot.amber { background: #ffaa00; }
    @keyframes pulse-green {
        0%, 100% { box-shadow: 0 0 4px rgba(0,255,136,0.3); }
        50% { box-shadow: 0 0 12px rgba(0,255,136,0.6); }
    }
    .status-dot.green.pulse { animation: pulse-green 2s infinite; }

    /* ─── Citations ─── */
    .citation-box {
        background: #111827; border-left: 3px solid #00d4ff;
        padding: 10px 16px; margin: 6px 0; border-radius: 0 8px 8px 0;
        font-size: 0.85rem; color: #e5e7eb;
    }

    /* ─── Consensus ─── */
    .consensus-box {
        background: rgba(0,255,136,0.05); border: 1px solid rgba(0,255,136,0.3);
        border-radius: 10px; padding: 20px; margin: 12px 0;
    }

    /* ─── Guardrail results ─── */
    .guardrail-pass {
        background: rgba(0,255,136,0.05); border: 1px solid rgba(0,255,136,0.2);
        padding: 16px; border-radius: 10px;
    }
    .guardrail-fail {
        background: rgba(255,51,102,0.05); border: 1px solid rgba(255,51,102,0.2);
        padding: 16px; border-radius: 10px;
    }

    /* ─── Page title ─── */
    .fs-title {
        font-size: 2rem; font-weight: 700; color: #f9fafb;
        margin-bottom: 0; line-height: 1.2;
    }
    .fs-subtitle {
        font-size: 1rem; color: #6b7280; margin-top: 2px; margin-bottom: 20px;
    }
    .fs-title-bar {
        height: 2px; margin: 8px 0 20px 0;
        background: linear-gradient(90deg, #00d4ff 0%, transparent 60%);
    }

    /* ─── Tables ─── */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* ─── Divider ─── */
    .fs-divider {
        border: none; border-top: 1px solid #1f2937;
        margin: 24px 0;
    }

    /* ─── Chat bubbles ─── */
    .chat-user {
        background: #1a2332; border: 1px solid #1f2937;
        border-radius: 12px 12px 4px 12px;
        padding: 12px 16px; margin: 8px 0; color: #e5e7eb;
    }
    .chat-assistant {
        background: #111827; border: 1px solid #1f2937;
        border-left: 3px solid #00d4ff;
        border-radius: 4px 12px 12px 12px;
        padding: 12px 16px; margin: 8px 0; color: #e5e7eb;
    }

    /* ─── Pipeline steps ─── */
    .pipeline-step {
        display: inline-flex; align-items: center; gap: 8px;
        padding: 8px 16px; border-radius: 8px;
        border: 1px solid #1f2937; background: #111827;
        font-size: 0.85rem; color: #6b7280;
    }
    .pipeline-step.active {
        border-color: #00d4ff; color: #00d4ff;
        box-shadow: 0 0 12px rgba(0,212,255,0.15);
    }
    .pipeline-step.done {
        border-color: rgba(0,255,136,0.3); color: #00ff88;
    }
    .pipeline-step.failed {
        border-color: rgba(255,51,102,0.3); color: #ff3366;
    }
    .pipeline-connector {
        display: inline-block; width: 32px; height: 2px;
        background: #1f2937; vertical-align: middle;
    }
    .pipeline-connector.done { background: #00ff88; }

    /* ─── Health cards ─── */
    .health-card {
        background: #111827; border: 1px solid #1f2937;
        border-radius: 10px; padding: 20px;
    }
    .health-card.healthy { border-left: 3px solid #00ff88; }
    .health-card.degraded { border-left: 3px solid #ffaa00; }
    .health-card.down { border-left: 3px solid #ff3366; }

    /* ─── Tabs ─── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: transparent;
        border-bottom: 1px solid #1f2937;
    }
    .stTabs [data-baseweb="tab"] {
        color: #6b7280;
        font-weight: 500;
        padding: 8px 20px;
    }
    .stTabs [aria-selected="true"] {
        color: #00d4ff !important;
        border-bottom: 2px solid #00d4ff !important;
    }

    /* ─── Buttons ─── */
    .stButton > button[kind="primary"] {
        background: #00d4ff; color: #0a0e17; font-weight: 600;
        border: none; border-radius: 6px;
    }
    .stButton > button[kind="primary"]:hover {
        background: #38bdf8;
    }

    /* ─── Selectbox / inputs ─── */
    .stSelectbox > div > div,
    .stTextInput > div > div > input,
    .stTextArea > div > textarea {
        background: #111827 !important;
        border-color: #1f2937 !important;
        color: #e5e7eb !important;
    }

    /* ─── Expander ─── */
    .streamlit-expanderHeader {
        color: #e5e7eb !important;
        background: #111827;
        border-color: #1f2937;
    }

    /* ─── Guardrail result -- amber for modified ─── */
    .guardrail-modified {
        background: rgba(255,170,0,0.05); border: 1px solid rgba(255,170,0,0.2);
        padding: 16px; border-radius: 10px;
    }

    /* ─── Pill buttons ─── */
    .pill-btn {
        display: inline-block;
        padding: 6px 16px;
        border: 1px solid rgba(0,212,255,0.3);
        border-radius: 999px;
        color: #00d4ff;
        font-size: 0.8rem;
        cursor: pointer;
        margin: 6px;
        background: transparent;
        transition: background 0.2s;
    }
    .pill-btn:hover {
        background: rgba(0,212,255,0.1);
    }
    </style>""", unsafe_allow_html=True)
