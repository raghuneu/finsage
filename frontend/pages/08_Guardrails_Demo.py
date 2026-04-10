import streamlit as st
from utils.connections import get_guardrail
from utils.styles import inject_css
from utils.helpers import page_header

inject_css()
guardrail = get_guardrail()

page_header("Guardrails Demo", "Test Bedrock Guardrails — content safety, PII redaction, and grounding checks")

if not guardrail:
    st.error("Set `BEDROCK_GUARDRAIL_ID` in your .env file to enable Guardrails.")
    st.stop()

EXAMPLES = {
    "Investment Advice (should block)": "You should buy AAPL stock right now, it's a guaranteed winner.",
    "Price Prediction (should block)": "AAPL will reach $500 next quarter based on my analysis.",
    "PII Detection (should mask)": "Contact john.doe@apple.com, SSN 123-45-6789 for more details.",
    "Clean Analysis (should pass)": "Apple reported 8% year-over-year revenue growth driven by Services segment expansion.",
    "Custom": "",
}

choice = st.selectbox("Select a scenario:", list(EXAMPLES.keys()))
text = st.text_area("Text to check:", value=EXAMPLES[choice], height=120)

if st.button("Check with Guardrails", type="primary") and text:
    with st.spinner("Running guardrail assessment..."):
        r = guardrail.check_output(text)

    if r.get("blocked"):
        st.markdown(
            '<div class="guardrail-fail">'
            '🛡️ <strong>BLOCKED</strong> — Content did not pass safety checks.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="guardrail-pass">'
            '✅ <strong>PASSED</strong> — Content is safe for publication.'
            '</div>',
            unsafe_allow_html=True,
        )

    details = r.get("details", [])
    if details:
        st.markdown("**Details:**")
        for d in details:
            st.markdown(f"- {d}")

    st.markdown("**Output:**")
    st.code(r.get("output", text))
