"""
Shared vision/LLM utilities for FinSage agents.

Provides Cortex-based chart critique with fallback:
    1. Primary: CORTEX_MODEL_VLM (default openai-gpt-5.2) via Snowflake Cortex
    2. Fallback: pixtral-large via Snowflake Cortex (if primary fails)

Both models are called through Snowflake Cortex COMPLETE() with
data_summary context enrichment for informed critique.
"""

import logging
import os

logger = logging.getLogger(__name__)

FALLBACK_VLM = "pixtral-large"


def cortex_complete(session, prompt: str, model: str = None) -> str:
    """
    Call Snowflake Cortex COMPLETE() with the given prompt.
    Returns the generated text string.
    """
    if model is None:
        model = os.getenv("CORTEX_MODEL_LLM", "claude-opus-4-6")
    safe = prompt.replace("'", "''")
    sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{safe}') AS r"
    rows = session.sql(sql).collect()
    raw = rows[0]["R"].strip() if rows and rows[0]["R"] else ""

    # Strip markdown code fences if LLM wraps output
    if "```" in raw:
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    return raw


def _format_data_summary(data_summary: dict) -> str:
    """Format data_summary dict into readable text for the Cortex fallback."""
    if not data_summary:
        return ""
    lines = []
    for key, val in data_summary.items():
        # Format numbers nicely
        if isinstance(val, float):
            lines.append(f"- {key}: {val:,.2f}")
        elif isinstance(val, int):
            lines.append(f"- {key}: {val:,}")
        else:
            lines.append(f"- {key}: {val}")
    return "\n".join(lines)


def vision_critique(
    session, image_path: str, prompt: str,
    data_summary: dict = None, model: str = None
) -> str:
    """
    Critique a chart using Cortex COMPLETE() with data context enrichment.

    Primary model: CORTEX_MODEL_VLM env var (default openai-gpt-5.2).
    Fallback: pixtral-large if the primary model fails.

    Args:
        session: Snowflake session
        image_path: Path to the rendered chart PNG (unused, kept for API compat)
        prompt: Critique prompt text
        data_summary: Dict of chart data metrics (for context enrichment)
        model: Override model for critique

    Returns:
        Critique text string
    """
    if model is None:
        model = os.getenv("CORTEX_MODEL_VLM", "openai-gpt-5.2")

    # Enrich prompt with data context
    context = _format_data_summary(data_summary)
    if context:
        enriched_prompt = (
            f"{prompt}\n\n"
            f"Chart data context (use this to evaluate the chart):\n{context}"
        )
    else:
        enriched_prompt = (
            f"{prompt}\n\n"
            f"[Note: Chart image not available for visual inspection. "
            f"Evaluate based on chart type and expected content.]"
        )

    # Try primary model
    try:
        result = cortex_complete(session, enriched_prompt, model=model)
        if result:
            logger.debug("VLM critique via Cortex %s", model)
            return result
    except Exception as e:
        logger.warning("Primary VLM model %s failed: %s — falling back to %s",
                       model, e, FALLBACK_VLM)

    # Fallback to pixtral-large
    try:
        result = cortex_complete(session, enriched_prompt, model=FALLBACK_VLM)
        if result:
            logger.debug("VLM critique via Cortex fallback %s", FALLBACK_VLM)
            return result
    except Exception as e:
        logger.error("Fallback VLM model %s also failed: %s", FALLBACK_VLM, e)

    return ""
