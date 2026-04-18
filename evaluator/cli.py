"""
FinSage Report Evaluator — CLI
==============================
Evaluates a pipeline output directory and prints a colour-coded score card.

Usage:
    # Evaluate with full LLM text scoring (needs Snowflake connection)
    python evaluator/cli.py outputs/AAPL_20260416_143000

    # Rule-based only (no Snowflake required)
    python evaluator/cli.py outputs/AAPL_20260416_143000 --no-llm

    # Save report card to a custom path
    python evaluator/cli.py outputs/AAPL_20260416_143000 --out my_eval.json

    # Evaluate the most-recent output directory automatically
    python evaluator/cli.py --latest
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Ensure Unicode output works on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Allow running as  python evaluator/cli.py  from project root
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from evaluator.evaluator import ReportEvaluator

# ── Colour helpers (no third-party deps) ──────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_CYAN   = "\033[96m"

_VERDICT_COLOUR = {
    "GOLDEN":             _GREEN,
    "PUBLICATION_READY":  _CYAN,
    "NEEDS_REVISION":     _YELLOW,
    "REJECTED":           _RED,
}

_SCORE_BAR_WIDTH = 30


def _bar(score: float, width: int = _SCORE_BAR_WIDTH) -> str:
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _colour_score(score: float) -> str:
    if score >= 90:
        return f"{_GREEN}{score:.1f}{_RESET}"
    if score >= 75:
        return f"{_CYAN}{score:.1f}{_RESET}"
    if score >= 50:
        return f"{_YELLOW}{score:.1f}{_RESET}"
    return f"{_RED}{score:.1f}{_RESET}"


def _print_report_card(card: dict) -> None:
    ticker  = card.get("ticker", "?")
    company = card.get("company_name", "")
    overall = card.get("overall_score", 0.0)
    verdict = card.get("verdict", "REJECTED")
    v_colour = _VERDICT_COLOUR.get(verdict, _RESET)

    label = f"{ticker}"
    if company:
        label += f" — {company}"

    print()
    print(f"{_BOLD}{'═' * 62}{_RESET}")
    print(f"{_BOLD}  FinSage Report Evaluation{_RESET}")
    print(f"  {label}")
    print(f"  {card.get('report_dir', '')}")
    print(f"{'─' * 62}")
    print(
        f"  {_BOLD}Overall Score:{_RESET}  "
        f"{_colour_score(overall)} / 100   "
        f"{_bar(overall)}"
    )
    print(
        f"  {_BOLD}Verdict:      {_RESET}  "
        f"{v_colour}{_BOLD}{verdict}{_RESET}"
    )
    llm_note = "(LLM scoring)" if card.get("llm_scoring") else "(rule-based only)"
    print(f"  {llm_note}")
    print(f"{'─' * 62}")
    print(f"  {'Dimension':<18} {'Score':>6}  {'Weight':>6}  {'Wtd':>5}  Bar")
    print(f"  {'─'*18} {'─'*6}  {'─'*6}  {'─'*5}  {'─'*20}")

    for dim, data in card.get("dimensions", {}).items():
        s   = data.get("score", 0.0)
        w   = data.get("weight", 0.0)
        ws  = data.get("weighted_score", 0.0)
        bar = _bar(s, 20)
        print(
            f"  {dim:<18} {_colour_score(s):>15}  {w:>6.0%}  {ws:>5.1f}  {bar}"
        )

    print(f"{'─' * 62}")
    recs = card.get("recommendations", [])
    if recs:
        print(f"  {_BOLD}Recommendations:{_RESET}")
        for r in recs:
            print(f"    • {r}")

    # Issue breakdown
    total_issues = sum(
        len(d.get("issues", []))
        for d in card.get("dimensions", {}).values()
    )
    if total_issues:
        print(f"{'─' * 62}")
        print(f"  {_BOLD}Issues ({total_issues} total):{_RESET}")
        for dim, data in card.get("dimensions", {}).items():
            for issue in data.get("issues", []):
                print(f"    [{dim}] {issue}")

    print(f"{'═' * 62}")
    print()


def _find_latest_output(outputs_dir: Path) -> Path:
    candidates = sorted(
        [d for d in outputs_dir.iterdir() if d.is_dir() and (d / "pipeline_result.json").exists()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No pipeline output directories found in {outputs_dir}")
    return candidates[0]


def _run_pdf_only(pdf_path: str) -> int:
    """Run just the PDF content check against a standalone PDF file."""
    from evaluator.checks.pdf_content import check_pdf_content

    p = Path(pdf_path)
    if not p.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    # Infer ticker from filename (e.g. MSFT_FinSage_Report_... → MSFT)
    ticker = p.stem.split("_")[0].upper()

    artifacts = {
        "pipeline_result": {"ticker": ticker, "pdf_path": str(p)},
        "chart_manifest": [],  # no manifest available — skips figure cross-validation
    }

    score, issues = check_pdf_content(artifacts)

    print()
    print(f"{_BOLD}{'=' * 62}{_RESET}")
    print(f"{_BOLD}  FinSage PDF Content Check (standalone){_RESET}")
    print(f"  Ticker inferred: {ticker}")
    print(f"  File: {p.name}")
    print(f"{'-' * 62}")
    print(f"  {_BOLD}PDF Score:{_RESET}  {_colour_score(score)} / 100   {_bar(score)}")
    print(f"{'-' * 62}")
    if issues:
        print(f"  {_BOLD}Issues ({len(issues)}):{_RESET}")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print(f"  {_GREEN}No issues found.{_RESET}")
    print(f"{'=' * 62}")
    print()
    print("  Note: full evaluation (data quality, text quality, consistency)")
    print("  requires the pipeline output directory with JSON sidecar files.")
    print()
    return 0 if score >= 75 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a FinSage report output directory for publication readiness.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        help="Path to the pipeline output directory (e.g. outputs/AAPL_20260416_143000)",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Auto-select the most-recently modified output directory under outputs/",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        dest="no_llm",
        help="Skip Cortex LLM text scoring — rule-based checks only (faster, no Snowflake needed)",
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        default=None,
        help="Custom path for the eval_report_card.json output (default: <output_dir>/eval_report_card.json)",
    )
    parser.add_argument(
        "--pdf-only",
        metavar="PDF_PATH",
        default=None,
        help="Run only the PDF content check against a standalone PDF file "
             "(no pipeline JSON files required)",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log verbosity (default: WARNING)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # ── PDF-only mode ─────────────────────────────────────────────────────
    if args.pdf_only:
        return _run_pdf_only(args.pdf_only)

    # Resolve output directory
    if args.latest:
        outputs_root = _PROJECT_ROOT / "outputs"
        try:
            resolved_dir = _find_latest_output(outputs_root)
            print(f"Auto-selected: {resolved_dir}")
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    elif args.output_dir:
        resolved_dir = Path(args.output_dir)
        if not resolved_dir.exists():
            print(f"Error: directory not found: {resolved_dir}", file=sys.stderr)
            return 1
    else:
        parser.print_help()
        return 1

    use_llm = not args.no_llm

    evaluator = ReportEvaluator(str(resolved_dir), use_llm=use_llm)
    card_path = evaluator.save_report_card(output_path=args.out)

    # Load the saved card for display (ensures we show what was written)
    with open(card_path, encoding="utf-8") as f:
        card = json.load(f)

    _print_report_card(card)
    print(f"  Report card saved to: {card_path}\n")

    # Exit code: 0 = GOLDEN or PUBLICATION_READY, 1 = NEEDS_REVISION or REJECTED
    verdict = card.get("verdict", "REJECTED")
    return 0 if verdict in ("GOLDEN", "PUBLICATION_READY") else 1


if __name__ == "__main__":
    sys.exit(main())
