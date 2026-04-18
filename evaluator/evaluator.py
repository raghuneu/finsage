"""
FinSage Report Evaluator
========================
Main orchestrator.  Loads pipeline output artifacts, runs all five evaluation
dimensions, and produces a structured eval_report_card.json.

Usage (programmatic):
    from evaluator import ReportEvaluator
    ev = ReportEvaluator("outputs/AAPL_20260416_143000")
    card = ev.evaluate()          # returns dict
    path = ev.save_report_card()  # writes eval_report_card.json

Usage (CLI):
    python evaluator/cli.py outputs/AAPL_20260416_143000
    python evaluator/cli.py outputs/AAPL_20260416_143000 --no-llm
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from evaluator.rubric import SCORE_WEIGHTS, get_verdict
from evaluator.checks.completeness import check_completeness
from evaluator.checks.data_quality   import check_data_quality
from evaluator.checks.chart_quality  import check_chart_quality
from evaluator.checks.consistency    import check_consistency
from evaluator.checks.text_quality   import check_text_quality
from evaluator.checks.pdf_content    import check_pdf_content

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> Optional[dict | list]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("File not found: %s", path)
        return None
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s", path, e)
        return None


def _generate_recommendations(results: dict[str, dict]) -> list[str]:
    """Distil the top actionable recommendations from dimension results."""
    recs = []

    # Completeness failures → re-run pipeline
    comp_issues = results.get("completeness", {}).get("issues", [])
    if comp_issues:
        recs.append(
            f"Re-run pipeline — {len(comp_issues)} completeness failure(s): "
            + "; ".join(comp_issues[:2])
            + ("..." if len(comp_issues) > 2 else "")
        )

    # Data quality problems → check upstream Snowflake data
    dq_issues = results.get("data_quality", {}).get("issues", [])
    if dq_issues:
        recs.append(
            f"Inspect Snowflake data — {len(dq_issues)} data quality issue(s): "
            + "; ".join(dq_issues[:2])
        )

    # Low-scoring charts → trigger re-render
    for issue in results.get("chart_quality", {}).get("issues", []):
        if "VLM score" in issue and "below threshold" in issue:
            chart_id = issue.split(":")[0].strip()
            recs.append(
                f"Regenerate chart '{chart_id}' — VLM score below acceptable threshold"
            )

    # Text quality issues → regenerate affected sections
    tq_issues = results.get("text_quality", {}).get("issues", [])
    if tq_issues:
        labels = sorted({i.split(":")[0].strip() for i in tq_issues})[:3]
        recs.append(
            f"Revise analysis text for: {', '.join(labels)} "
            f"({len(tq_issues)} text quality issue(s))"
        )

    # Consistency issues → review prompt / data alignment
    cons_issues = results.get("consistency", {}).get("issues", [])
    if cons_issues:
        recs.append(
            f"Review text-data consistency — {len(cons_issues)} mismatch(es) found: "
            + "; ".join(cons_issues[:2])
        )

    # PDF content issues → re-run pipeline or investigate upstream data
    pdf_issues = results.get("pdf_content", {}).get("issues", [])
    if pdf_issues:
        recs.append(
            f"PDF content validation failed ({len(pdf_issues)} issue(s)) — "
            "check for $0 values or missing sections: "
            + "; ".join(pdf_issues[:2])
        )

    return recs or ["No critical issues found — report is ready for publication."]


class ReportEvaluator:
    """
    Evaluates a FinSage pipeline output directory for publication readiness.

    Args:
        output_dir: Path to the report output directory (contains
                    pipeline_result.json, chart_manifest.json, PNGs, PDF).
        use_llm:    If True and a Snowflake session can be established,
                    Cortex is used for text quality scoring.  Defaults to True.
    """

    def __init__(self, output_dir: str, use_llm: bool = True):
        self.output_dir = Path(output_dir).resolve()
        self.use_llm = use_llm
        self._session = None
        self._session_tried = False
        self._artifacts: Optional[dict] = None

    # ── Artifact loading ───────────────────────────────────────────────────

    def _load_artifacts(self) -> dict:
        if self._artifacts is not None:
            return self._artifacts

        pipeline_path  = self.output_dir / "pipeline_result.json"
        manifest_path  = self.output_dir / "chart_manifest.json"
        analysis_path  = self.output_dir / "analysis_result.json"

        pipeline = _load_json(pipeline_path)
        analysis = _load_json(analysis_path)

        # Backwards-compat: old pipeline_result format embedded full analysis text.
        # New format (post-observability refactor) keeps only a summary and writes
        # analysis text to analysis_result.json.  Prefer the dedicated file; fall
        # back to pipeline_result for runs produced before the refactor.
        if analysis is None and isinstance(pipeline, dict) and "analysis" in pipeline:
            analysis = {**pipeline.get("analysis", {})}
            # Old format kept company_overview / peer_comparison at pipeline root
            for key in ("company_overview", "peer_comparison"):
                if key in pipeline:
                    analysis[key] = pipeline[key]
            logger.debug("Using legacy inline analysis from pipeline_result.json")

        self._artifacts = {
            "output_dir":      str(self.output_dir),
            "pipeline_result": pipeline,
            "chart_manifest":  _load_json(manifest_path),
            "analysis_result": analysis,  # may be None if both sources missing
        }
        return self._artifacts

    # ── Snowflake session (lazy, optional) ────────────────────────────────

    def _get_session(self):
        if self._session_tried:
            return self._session
        self._session_tried = True
        try:
            # Add scripts/ to path (same approach as orchestrator.py)
            scripts_dir = str(Path(__file__).parent.parent / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            from snowflake_connection import get_session
            self._session = get_session()
            logger.info("Snowflake session established for LLM text scoring")
        except Exception as e:
            logger.warning(
                "Could not connect to Snowflake — text quality will use rule-based scoring only. (%s)", e
            )
        return self._session

    # ── Main evaluation ────────────────────────────────────────────────────

    def evaluate(self) -> dict:
        """
        Run all evaluation dimensions and return the complete report card dict.
        """
        artifacts = self._load_artifacts()
        pipeline = artifacts.get("pipeline_result") or {}
        ticker = pipeline.get("ticker", "UNKNOWN")
        company = pipeline.get("company_name", "")

        logger.info("═" * 60)
        logger.info("Evaluating report: %s  (%s)", ticker, self.output_dir.name)
        logger.info("═" * 60)

        # ── Run all dimensions ─────────────────────────────────────────
        session = self._get_session() if self.use_llm else None

        dim_results: dict[str, dict] = {}

        for name, fn, needs_session in (
            ("completeness",  check_completeness,  False),
            ("data_quality",  check_data_quality,  False),
            ("chart_quality", check_chart_quality, False),
            ("consistency",   check_consistency,   False),
            ("pdf_content",   check_pdf_content,   False),
            ("text_quality",  None,                True),
        ):
            logger.info("Running dimension: %s", name)
            if name == "text_quality":
                score, issues = check_text_quality(artifacts, session)
            else:
                score, issues = fn(artifacts)

            dim_results[name] = {
                "score":          round(score, 1),
                "weight":         SCORE_WEIGHTS[name],
                "weighted_score": round(score * SCORE_WEIGHTS[name], 1),
                "issues":         issues,
            }
            logger.info("  → %.1f  (%d issues)", score, len(issues))

        # ── Aggregate overall score ────────────────────────────────────
        overall = sum(
            dim_results[d]["score"] * SCORE_WEIGHTS[d]
            for d in SCORE_WEIGHTS
        )
        verdict = get_verdict(overall)
        recommendations = _generate_recommendations(dim_results)

        card = {
            "ticker":         ticker,
            "company_name":   company,
            "run_id":         pipeline.get("run_id"),
            "report_dir":     str(self.output_dir),
            "evaluated_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "llm_scoring":    session is not None,
            "overall_score":  round(overall, 1),
            "verdict":        verdict,
            "dimensions":     dim_results,
            "recommendations": recommendations,
        }

        logger.info("═" * 60)
        logger.info("VERDICT: %s  (overall %.1f / 100)", verdict, overall)
        logger.info("═" * 60)

        return card

    def save_report_card(self, output_path: Optional[str] = None) -> str:
        """
        Run evaluation and write eval_report_card.json.

        Returns the path of the written file.
        """
        card = self.evaluate()
        path = Path(output_path) if output_path else (self.output_dir / "eval_report_card.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(card, f, indent=2, ensure_ascii=False)
        logger.info("Report card written to %s", path)
        return str(path)
