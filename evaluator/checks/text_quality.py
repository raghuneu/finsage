"""
Text Quality Check
==================
Two-stage evaluation of all LLM-generated text in the report:

Stage 1 (always runs) — Rule-based checks:
    - Word count within bounds
    - No markdown artifacts (**bold**, `code`, # headers, * bullets)
    - No fallback/guardrail placeholder text
    - At least one numeric figure per paragraph

Stage 2 (runs when a Snowflake session is provided) — LLM scoring via Cortex:
    - Each chart analysis is scored by claude-opus-4-6 on three axes:
        SPECIFICITY   (0-10): cites specific numbers from the data
        PROFESSIONALISM (0-10): institutional-grade writing quality
        ACCURACY      (0-10): aligns with / not contradicted by the data
    - Score = mean of the three axes, normalised to 0-100

Final score = weighted average of rule score (40%) and LLM score (60%).
If no session is provided, only the rule score is used (normalised to 100).
"""

import re
import os
import logging
from typing import Optional

from evaluator.rubric import (
    REQUIRED_CHART_IDS,
    REQUIRED_TEXT_FIELDS,
    ANALYSIS_MIN_WORDS,
    ANALYSIS_MAX_WORDS,
    FALLBACK_SUBSTRINGS,
)

logger = logging.getLogger(__name__)

_CORTEX_MODEL = os.getenv("CORTEX_MODEL_LLM", "claude-opus-4-6")

# Markdown patterns that should not appear in final report text
_MARKDOWN_PATTERNS = [
    re.compile(r"\*\*[^*]+\*\*"),   # **bold**
    re.compile(r"`[^`]+`"),          # `code`
    re.compile(r"^\s*#+\s", re.M),  # # Heading
    re.compile(r"^\s*\*\s", re.M),  # * bullet
    re.compile(r"^\s*-\s", re.M),   # - bullet
    re.compile(r"^\s*\d+\.\s", re.M),  # 1. ordered list
]

_NUMBER_PATTERN = re.compile(r"\d")


def _get_nested(obj: dict, dot_path: str):
    keys = dot_path.split(".")
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _is_fallback(text: str) -> bool:
    lower = text.lower()
    return any(sub in lower for sub in FALLBACK_SUBSTRINGS)


# ── Rule-based scoring ─────────────────────────────────────────────────────

def _rule_score_text(text: str, label: str) -> tuple[float, list[str]]:
    """
    Score a single text string on rule-based criteria.
    Returns (score 0-10, issues).
    """
    issues = []
    deductions = 0.0
    max_deductions = 10.0

    # Fallback / guardrail placeholder — immediate zero
    if _is_fallback(text):
        return 0.0, [f"{label}: contains fallback/guardrail placeholder text"]

    # Word count
    words = text.split()
    wc = len(words)
    if wc < ANALYSIS_MIN_WORDS:
        issues.append(f"{label}: too short ({wc} words, min {ANALYSIS_MIN_WORDS})")
        deductions += 3.0
    elif wc > ANALYSIS_MAX_WORDS:
        issues.append(f"{label}: too long ({wc} words, max {ANALYSIS_MAX_WORDS})")
        deductions += 1.0

    # Markdown artifacts
    for pattern in _MARKDOWN_PATTERNS:
        if pattern.search(text):
            issues.append(f"{label}: contains markdown formatting ({pattern.pattern!r})")
            deductions += 2.0
            break  # count once per field

    # Must contain at least one numeric figure
    if not _NUMBER_PATTERN.search(text):
        issues.append(f"{label}: no numeric figures found in text")
        deductions += 2.0

    score = max(0.0, max_deductions - deductions)
    return score, issues


# ── LLM scoring via Cortex ─────────────────────────────────────────────────

_EVAL_PROMPT_TEMPLATE = """\
You are a senior equity research editor assessing the quality of an AI-generated \
financial analysis paragraph for inclusion in an institutional research report.

Chart context: {chart_label}
Key data provided to the analyst:
{data_summary_text}

Analysis text to evaluate:
\"\"\"{analysis_text}\"\"\"

Score the analysis on exactly three criteria (integer 0-10 each):
  SPECIFICITY: Does it reference specific numbers/percentages from the provided data? \
(0 = no numbers cited, 10 = all key figures cited and explained)
  PROFESSIONALISM: Is it institutional-grade prose — third person, no bullets, \
analytical not descriptive? (0 = casual/vague, 10 = Goldman Sachs quality)
  ACCURACY: Does the interpretation align with the data? \
(0 = contradicts data, 10 = fully consistent and insightful)

Respond in EXACTLY this format with no other text:
SPECIFICITY: <integer>
PROFESSIONALISM: <integer>
ACCURACY: <integer>
"""


def _parse_llm_scores(response: str) -> dict[str, float]:
    result = {}
    for label in ("SPECIFICITY", "PROFESSIONALISM", "ACCURACY"):
        m = re.search(rf"{label}:\s*(\d+)", response, re.IGNORECASE)
        if m:
            result[label] = min(10.0, max(0.0, float(m.group(1))))
    return result


def _cortex_complete(session, prompt: str) -> str:
    safe = prompt.replace("'", "''")
    sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{_CORTEX_MODEL}', '{safe}') AS r"
    try:
        rows = session.sql(sql).collect()
        return (rows[0]["R"] or "").strip()
    except Exception as e:
        logger.warning("Cortex call failed: %s", e)
        return ""


def _llm_score_text(
    session,
    chart_label: str,
    analysis_text: str,
    data_summary: dict,
) -> tuple[float, list[str]]:
    """
    Score a single analysis paragraph via Cortex.
    Returns (score 0-10, issues).
    """
    if not analysis_text:
        return 0.0, [f"{chart_label}: empty text, cannot score"]

    # Format data_summary as readable lines
    ds_lines = "\n".join(f"  {k}: {v}" for k, v in data_summary.items() if v is not None)
    if not ds_lines:
        ds_lines = "  (no data summary available)"

    prompt = _EVAL_PROMPT_TEMPLATE.format(
        chart_label=chart_label,
        data_summary_text=ds_lines,
        analysis_text=analysis_text[:1500],  # cap to avoid prompt overflow
    )

    response = _cortex_complete(session, prompt)
    if not response:
        return 7.0, []  # neutral default on Cortex failure

    scores = _parse_llm_scores(response)
    if not scores:
        logger.warning("Could not parse Cortex scores for %s: %r", chart_label, response[:200])
        return 7.0, []

    mean_score = sum(scores.values()) / len(scores)
    issues = []

    if scores.get("SPECIFICITY", 10) < 5:
        issues.append(f"{chart_label}: low specificity ({scores['SPECIFICITY']:.0f}/10) — add specific figures")
    if scores.get("PROFESSIONALISM", 10) < 6:
        issues.append(f"{chart_label}: low professionalism ({scores['PROFESSIONALISM']:.0f}/10)")
    if scores.get("ACCURACY", 10) < 6:
        issues.append(f"{chart_label}: low accuracy ({scores['ACCURACY']:.0f}/10) — analysis may contradict data")

    return mean_score, issues


# ── Main entrypoint ────────────────────────────────────────────────────────

def check_text_quality(
    artifacts: dict,
    session=None,
) -> tuple[float, list[str]]:
    """
    Args:
        artifacts: dict with 'pipeline_result' and 'chart_manifest'
        session:   Snowflake session for LLM scoring, or None for rule-only mode

    Returns:
        (score 0-100, list of issue strings)
    """
    pipeline = artifacts.get("pipeline_result") or {}
    manifest = artifacts.get("chart_manifest") or []

    charts_by_id = {c.get("chart_id"): c for c in manifest}
    chart_analyses = {
        a.get("chart_id"): a.get("analysis_text", "")
        for a in (pipeline.get("analysis", {}).get("chart_analyses") or [])
    }

    all_issues: list[str] = []
    rule_scores: list[float] = []
    llm_scores: list[float] = []

    use_llm = session is not None
    if not use_llm:
        logger.info("Text quality: running rule-based checks only (no Snowflake session)")

    # ── Score per-chart analysis texts ────────────────────────────────────
    for chart_id in REQUIRED_CHART_IDS:
        text = chart_analyses.get(chart_id, "")
        data_summary = (charts_by_id.get(chart_id) or {}).get("data_summary") or {}

        r_score, r_issues = _rule_score_text(text, chart_id)
        rule_scores.append(r_score)
        all_issues.extend(r_issues)

        if use_llm and text and not _is_fallback(text):
            l_score, l_issues = _llm_score_text(
                session,
                chart_id,
                text,
                data_summary,
            )
            llm_scores.append(l_score)
            all_issues.extend(l_issues)

    # ── Score section-level text fields ───────────────────────────────────
    for dot_path in REQUIRED_TEXT_FIELDS:
        text = _get_nested(pipeline, dot_path) or ""
        r_score, r_issues = _rule_score_text(text, dot_path)
        rule_scores.append(r_score)
        all_issues.extend(r_issues)

        if use_llm and text and not _is_fallback(text):
            l_score, l_issues = _llm_score_text(
                session,
                dot_path,
                text,
                {},
            )
            llm_scores.append(l_score)
            all_issues.extend(l_issues)

    # ── Aggregate ─────────────────────────────────────────────────────────
    rule_avg = (sum(rule_scores) / len(rule_scores)) if rule_scores else 0.0
    rule_pct = rule_avg * 10.0  # 0-10 → 0-100

    if llm_scores:
        llm_avg = sum(llm_scores) / len(llm_scores)
        llm_pct = llm_avg * 10.0
        score = rule_pct * 0.40 + llm_pct * 0.60
    else:
        score = rule_pct

    logger.info(
        "Text quality: rule=%.1f, llm=%s → %.1f",
        rule_pct,
        f"{(sum(llm_scores)/len(llm_scores)*10):.1f}" if llm_scores else "N/A",
        score,
    )
    return round(score, 1), all_issues
