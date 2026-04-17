"""
Shared vision/LLM utilities for FinSage agents.

Provides Cortex-based chart critique using true multimodal image input:
    1. Upload chart PNG to a Snowflake internal stage
    2. Call CORTEX COMPLETE() with TO_FILE() for real visual inspection
    3. Fallback to text-only critique if stage/upload fails

Primary VLM: CORTEX_MODEL_VLM env var (default claude-sonnet-4-6)
Fallback VLM: pixtral-large via Snowflake Cortex
"""

import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

FALLBACK_VLM = "pixtral-large"
CHART_STAGE = "FINSAGE_DB.RAW.CHART_IMAGES_STAGE"
_stage_ensured = False
_stage_lock = threading.Lock()


def ensure_chart_stage(session) -> None:
    """Create the internal stage for chart images if it doesn't exist."""
    global _stage_ensured
    if _stage_ensured:
        return
    with _stage_lock:
        if _stage_ensured:          # double-checked locking
            return
        session.sql(
            f"CREATE STAGE IF NOT EXISTS {CHART_STAGE} "
            f"DIRECTORY = (ENABLE = TRUE) "
            f"ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')"
        ).collect()
        _stage_ensured = True
        logger.info("Chart image stage ensured: %s", CHART_STAGE)


def upload_chart_to_stage(session, local_path: str) -> str:
    """Upload a chart PNG to the Snowflake stage.

    Returns the stage filename (just the basename) for use with TO_FILE().
    """
    ensure_chart_stage(session)
    fname = Path(local_path).name
    session.file.put(
        local_path,
        f"@{CHART_STAGE}",
        auto_compress=False,
        overwrite=True,
    )
    logger.debug("Uploaded chart to stage: %s -> @%s/%s", local_path, CHART_STAGE, fname)
    return fname


def cortex_complete(session, prompt: str, model: str = None) -> str:
    """
    Call Snowflake Cortex COMPLETE() with the given prompt (text-only).

    Uses the 2-arg form COMPLETE(model, prompt) which returns a plain string.
    Snowflake's default temperature is already 0, so no options needed.

    Args:
        session: Snowflake session
        prompt: The prompt text
        model: Override model (default from CORTEX_MODEL_LLM env var)

    Returns the generated text string.
    """
    if model is None:
        model = os.getenv("CORTEX_MODEL_LLM", "claude-opus-4-6")
    safe = prompt.replace("'", "''")
    sql = (
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{safe}') AS r"
    )
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


def _cortex_complete_multimodal(
    session, prompt: str, stage_filename: str, model: str,
) -> str:
    """Call Cortex COMPLETE() with a chart image via TO_FILE() for true visual critique.

    Uses the 3-arg multimodal form: COMPLETE(model, prompt, file).
    The multimodal variant does not support an options parameter.
    """
    safe = prompt.replace("'", "''")
    sql = (
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE("
        f"'{model}', "
        f"'{safe}', "
        f"TO_FILE('@{CHART_STAGE}', '{stage_filename}')"
        f") AS r"
    )
    rows = session.sql(sql).collect()
    raw = rows[0]["R"].strip() if rows and rows[0]["R"] else ""

    if "```" in raw:
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    return raw


def _format_data_summary(data_summary: dict) -> str:
    """Format data_summary dict into readable text for prompt enrichment."""
    if not data_summary:
        return ""
    lines = []
    for key, val in data_summary.items():
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
    Critique a chart using Cortex COMPLETE() multimodal with the actual chart image.

    Uploads the chart PNG to a Snowflake stage and calls COMPLETE() with
    TO_FILE() so the VLM can visually inspect the rendered chart.

    Falls back to text-only critique if the multimodal call fails.

    Args:
        session: Snowflake session
        image_path: Path to the rendered chart PNG
        prompt: Critique prompt text
        data_summary: Dict of chart data metrics (for context enrichment)
        model: Override model for critique

    Returns:
        Critique text string
    """
    if model is None:
        model = os.getenv("CORTEX_MODEL_VLM", "claude-sonnet-4-6")

    # Enrich prompt with data context
    context = _format_data_summary(data_summary)
    enriched_prompt = prompt
    if context:
        enriched_prompt = (
            f"{prompt}\n\n"
            f"Chart data context (use this alongside the visual inspection):\n{context}"
        )

    # Try multimodal critique (upload image + TO_FILE)
    if image_path and os.path.exists(image_path):
        try:
            stage_filename = upload_chart_to_stage(session, image_path)
            result = _cortex_complete_multimodal(
                session, enriched_prompt, stage_filename, model=model
            )
            if result:
                logger.info("VLM critique via Cortex multimodal %s (image: %s)",
                            model, stage_filename)
                return result
        except Exception as e:
            logger.warning(
                "Multimodal VLM critique failed with %s: %s — falling back to text-only",
                model, e
            )

        # Fallback: try multimodal with pixtral-large (supports single image)
        if model != FALLBACK_VLM:
            try:
                stage_filename = upload_chart_to_stage(session, image_path)
                result = _cortex_complete_multimodal(
                    session, enriched_prompt, stage_filename, model=FALLBACK_VLM
                )
                if result:
                    logger.info("VLM critique via Cortex multimodal fallback %s",
                                FALLBACK_VLM)
                    return result
            except Exception as e:
                logger.warning(
                    "Fallback multimodal VLM %s also failed: %s — using text-only",
                    FALLBACK_VLM, e
                )

    # Final fallback: text-only critique (no image)
    logger.warning("Falling back to text-only critique (no image sent to VLM)")
    if not context:
        enriched_prompt = (
            f"{prompt}\n\n"
            f"[Note: Chart image not available for visual inspection. "
            f"Evaluate based on chart type and expected content.]"
        )

    try:
        result = cortex_complete(session, enriched_prompt, model=model)
        if result:
            logger.debug("VLM critique via text-only Cortex %s", model)
            return result
    except Exception as e:
        logger.warning("Text-only critique with %s failed: %s", model, e)

    try:
        result = cortex_complete(session, enriched_prompt, model=FALLBACK_VLM)
        if result:
            logger.debug("VLM critique via text-only fallback %s", FALLBACK_VLM)
            return result
    except Exception as e:
        logger.error("All critique methods failed: %s", e)

    return ""
