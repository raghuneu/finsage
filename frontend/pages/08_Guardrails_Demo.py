"""FinSage Guardrails Demo -- Test Bedrock Guardrails for content safety."""

import streamlit as st
from utils.connections import get_guardrail
from utils.styles import inject_css
from utils.helpers import page_header, section_header

inject_css()
guardrail = get_guardrail()

page_header("Guardrails Demo", "Test Bedrock Guardrails -- content safety, PII redaction, and grounding checks")

if not guardrail:
    st.markdown(
        '<div class="fs-card fs-card-accent">'
        '<h4>Guardrails Not Configured</h4>'
        '<div style="color:#6b7280;font-size:0.85rem;line-height:1.6">'
        'Create a guardrail in the AWS Bedrock console, then set '
        '<code>BEDROCK_GUARDRAIL_ID</code> in your <code>.env</code> file. '
        'Ensure valid AWS credentials are configured.'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Active guardrail info ───────────────────────────────────
st.markdown(
    f'<div class="fs-card">'
    f'<h4>Active Guardrail</h4>'
    f'<div style="color:#f9fafb;font-size:0.9rem">'
    f'<span class="status-dot green pulse"></span> '
    f'ID: <code>{guardrail.guardrail_id}</code> &nbsp; | &nbsp; '
    f'Version: <code>{getattr(guardrail, "guardrail_version", "DRAFT")}</code>'
    f'</div></div>',
    unsafe_allow_html=True,
)

# ── Scenario presets (card grid) ───────────────────────────
section_header("Test Scenarios", "Select a preset or enter custom text to test guardrail behavior")

EXAMPLES = {
    "Investment Advice": (
        "You should buy AAPL stock right now, it's a guaranteed winner.",
        "Tests denied-topics filter", "block",
    ),
    "Price Prediction": (
        "AAPL will reach $500 next quarter based on my analysis.",
        "Tests denied-topics filter", "block",
    ),
    "PII Detection": (
        "Contact john.doe@apple.com, SSN 123-45-6789 for more details.",
        "Tests PII redaction filter", "redact",
    ),
    "Clean Analysis": (
        "Apple reported 8% year-over-year revenue growth driven by Services segment expansion.",
        "Tests legitimate analysis passes", "pass",
    ),
    "Mixed Content": (
        "Apple's revenue grew 8% YoY. You should invest everything in AAPL immediately.",
        "Tests mixed valid + investment advice", "block",
    ),
    "Custom": (
        "",
        "Enter your own text", "custom",
    ),
}

# Render as 2x3 card grid
keys = list(EXAMPLES.keys())
for row_start in range(0, len(keys), 3):
    cols = st.columns(3)
    for i, col in enumerate(cols):
        idx = row_start + i
        if idx < len(keys):
            key = keys[idx]
            _, desc, expected = EXAMPLES[key]
            icon_map = {"block": "🚫", "redact": "🔒", "pass": "✅", "custom": "✏️"}
            border_map = {"block": "#ff3366", "redact": "#ffaa00", "pass": "#00ff88", "custom": "#00d4ff"}
            with col:
                if st.button(
                    f"{icon_map.get(expected, '')} {key}",
                    key=f"scenario_{idx}",
                    use_container_width=True,
                ):
                    st.session_state["guardrail_scenario"] = key

selected = st.session_state.get("guardrail_scenario", "Custom")
example_text, description, _ = EXAMPLES.get(selected, EXAMPLES["Custom"])

st.markdown(f'<div style="color:#6b7280;font-size:0.8rem;margin:8px 0">{description}</div>', unsafe_allow_html=True)

text = st.text_area(
    "Text to check:",
    value=example_text,
    height=120,
    placeholder="Enter text to check against guardrails...",
)

col_btn, _ = st.columns([1, 3])
with col_btn:
    run_check = st.button("Check with Guardrails", type="primary")

if run_check and text:
    with st.spinner("Running guardrail assessment..."):
        try:
            r = guardrail.check_output(text)
        except Exception as e:
            st.error(f"Guardrail check failed: {e}")
            st.stop()

    is_blocked = r.get("blocked", False)

    if is_blocked:
        st.markdown(
            '<div class="guardrail-fail" style="text-align:center;padding:24px">'
            '<div style="font-size:2rem;margin-bottom:8px">🚫</div>'
            '<div style="color:#ff3366;font-size:1.2rem;font-weight:700">BLOCKED</div>'
            '<div style="color:#6b7280;font-size:0.85rem;margin-top:4px">'
            'Content did not pass safety checks</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="guardrail-pass" style="text-align:center;padding:24px">'
            '<div style="font-size:2rem;margin-bottom:8px">✅</div>'
            '<div style="color:#00ff88;font-size:1.2rem;font-weight:700">PASSED</div>'
            '<div style="color:#6b7280;font-size:0.85rem;margin-top:4px">'
            'Content passed all safety checks</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # Details
    details = r.get("details", [])
    action = r.get("action", r.get("guardrail_action", ""))

    if action or details:
        section_header("Assessment Details")
        if action:
            st.markdown(f"**Guardrail Action:** `{action}`")
        if details:
            for d in details:
                if isinstance(d, dict):
                    dtype = d.get("type", "Assessment")
                    msg = d.get("message", str(d))
                    st.markdown(f'<div class="citation-box"><strong style="color:#00d4ff">{dtype}:</strong> {msg}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="citation-box">{d}</div>', unsafe_allow_html=True)

    # Output text
    section_header("Output Text")
    output_text = r.get("output", text)
    if output_text != text:
        st.markdown('<div style="color:#6b7280;font-size:0.8rem">Guardrail modified the text (e.g., PII redaction):</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#6b7280;font-size:0.8rem">Text passed through without modification:</div>', unsafe_allow_html=True)
    st.code(output_text, language=None)

    with st.expander("Raw guardrail response"):
        st.json(r)

elif run_check and not text:
    st.markdown('<div style="color:#ffaa00;font-size:0.85rem">Enter some text to check.</div>', unsafe_allow_html=True)

# ── How it works ────────────────────────────────────────────
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)

with st.expander("How FinSage Guardrails Work"):
    st.markdown("""
**Bedrock Guardrails** are applied to all LLM-generated content in FinSage to ensure safety and accuracy:

| Check | Description |
|-------|-------------|
| **Denied Topics** | Blocks direct investment advice and price predictions |
| **PII Redaction** | Masks emails, SSNs, phone numbers, and other sensitive data |
| **Contextual Grounding** | Detects hallucinations by checking if claims are supported by source data |
| **Content Filters** | Blocks harmful, misleading, or inappropriate content |

All guardrail checks run in real-time with sub-second latency.
""")
