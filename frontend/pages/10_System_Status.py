import os
import streamlit as st
from utils.connections import get_snowflake, get_kb, get_guardrail, get_multi_model
from utils.styles import inject_css
from utils.helpers import page_header, section_header

inject_css()
session = get_snowflake()
kb = get_kb()
guardrail = get_guardrail()
mm = get_multi_model()

page_header("System Status", "Health checks for all connected services")

c1, c2 = st.columns(2)

with c1:
    section_header("Snowflake")
    if session:
        st.success("Connected")
        try:
            info = session.sql(
                "SELECT CURRENT_USER() u, CURRENT_ROLE() r, "
                "CURRENT_WAREHOUSE() w, CURRENT_DATABASE() d"
            ).collect()[0]
            st.markdown(f"**User:** {info['U']}")
            st.markdown(f"**Role:** {info['R']}")
            st.markdown(f"**Warehouse:** {info['W']}")
            st.markdown(f"**Database:** {info['D']}")
        except Exception:
            pass
    else:
        st.error("Not connected — check .env credentials")

    section_header("AWS Identity")
    try:
        import boto3
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        st.success(f"Account: {identity['Account']}")
        st.markdown(f"**ARN:** `{identity['Arn']}`")
    except Exception as e:
        st.error(f"AWS: {e}")

with c2:
    section_header("Bedrock Knowledge Base")
    if kb:
        try:
            h = kb.health_check()
            if h.get("status") == "healthy":
                st.success(f"Healthy — `{h['kb_id']}`")
            else:
                st.error(h.get("error", "Unknown error"))
        except Exception as e:
            st.error(str(e))
    else:
        st.warning("Not configured — set BEDROCK_KB_ID")

    section_header("Guardrails")
    if guardrail:
        st.success(f"Active — `{guardrail.guardrail_id}`")
    else:
        st.warning("Not configured — set BEDROCK_GUARDRAIL_ID")

    section_header("Multi-Model Analyzer")
    if mm:
        st.success(f"{len(mm.models)} models configured")
        for m in mm.models:
            st.markdown(f"- `{m}`")
    else:
        st.warning("Not configured — check AWS credentials")

# ── Environment Variables ────────────────────────────────────
st.markdown('<hr class="fs-divider">', unsafe_allow_html=True)
section_header("Environment Variables")

env_vars = [
    "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_DATABASE",
    "FINSAGE_S3_BUCKET", "BEDROCK_KB_ID", "BEDROCK_GUARDRAIL_ID",
    "BEDROCK_MODEL_ID", "AWS_DEFAULT_REGION",
]

cols = st.columns(2)
for i, v in enumerate(env_vars):
    val = os.getenv(v, "")
    with cols[i % 2]:
        if val:
            display = val[:25] + "..." if len(val) > 25 else val
            st.markdown(f"<span class='status-dot green'></span> `{v}` = `{display}`", unsafe_allow_html=True)
        else:
            st.markdown(f"<span class='status-dot red'></span> `{v}` — not set", unsafe_allow_html=True)
