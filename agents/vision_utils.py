"""
Shared vision/LLM utilities for FinSage agents.

Provides a dual-backend vision critique function:
    1. Gemini 2.0 Flash (real multimodal — sends actual chart image)
    2. Cortex text-only fallback (enriched with data_summary context)

The Snowflake EDU account does NOT support image input via Cortex,
so Gemini is required for true VLM chart critique.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Cache the Gemini client across calls
_gemini_client = None
_gemini_checked = False


def _get_gemini_client():
    """Lazy-load Gemini client. Returns None if unavailable."""
    global _gemini_client, _gemini_checked
    if _gemini_checked:
        return _gemini_client

    _gemini_checked = True
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.info("GEMINI_API_KEY not set — VLM will use Cortex text-only fallback")
        return None

    try:
        from google import genai
        _gemini_client = genai.Client(api_key=api_key)
        logger.info("Gemini client initialized — real VLM image critique enabled")
        return _gemini_client
    except ImportError:
        logger.warning("google-genai not installed — run: pip install google-genai")
        return None
    except Exception as e:
        logger.warning(f"Gemini client init failed: {e}")
        return None


def cortex_complete(session, prompt: str, model: str = "mistral-large") -> str:
    """
    Call Snowflake Cortex COMPLETE() with the given prompt.
    Returns the generated text string.
    """
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


def _gemini_critique(image_path: str, prompt: str) -> str:
    """Send image + prompt to Gemini 2.0 Flash for real multimodal critique."""
    from google.genai import types

    client = _get_gemini_client()
    if not client:
        return ""

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            types.Part.from_text(text=prompt),
        ],
    )
    return response.text.strip() if response.text else ""


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
    data_summary: dict = None, model: str = "pixtral-large"
) -> str:
    """
    Critique a chart using the best available vision backend.

    1. If Gemini is available: sends the actual chart image (real VLM).
    2. If Gemini unavailable: uses Cortex text-only with data_summary
       context so the critique has concrete data about chart contents.

    Args:
        session: Snowflake session (for Cortex fallback)
        image_path: Path to the rendered chart PNG
        prompt: Critique prompt text
        data_summary: Dict of chart data metrics (for Cortex enrichment)
        model: Cortex model for text-only fallback

    Returns:
        Critique text string
    """
    # Try Gemini first (real image critique)
    client = _get_gemini_client()
    if client and os.path.exists(image_path):
        try:
            result = _gemini_critique(image_path, prompt)
            if result:
                logger.debug("VLM critique via Gemini (real image)")
                return result
        except Exception as e:
            logger.warning(f"Gemini critique failed, falling back to Cortex: {e}")

    # Cortex fallback — enrich prompt with data context
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

    logger.debug("VLM critique via Cortex text-only (enriched with data_summary)")
    return cortex_complete(session, enriched_prompt, model=model)
