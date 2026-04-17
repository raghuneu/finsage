---
name: cavm-pipeline
description: FinSage CAVM (Chart-Analysis-Validation-Metrics) multi-agent report generation pipeline
---

# CAVM Pipeline Guide

Reference for the FinSage multi-agent report generation pipeline: **Chart → Analysis → Validation → Metrics**.

## Pipeline Overview

```
Orchestrator (agents/orchestrator.py)
├── ChartAgent (agents/chart_agent.py)          — Generate 8 chart images
│   ├── chart_data_prep.py                      — Deterministic data prep
│   ├── chart_specs.py                          — Chart specifications
│   └── chart_validation.py                     — Pre-render validation
├── ValidationAgent (agents/validation_agent.py) — Two-tier chart validation
├── AnalysisAgent (agents/analysis_agent.py)     — Chain-of-Analysis text
└── ReportAgent (agents/report_agent.py)         — PDF report assembly
```

## Orchestrator

**File**: `agents/orchestrator.py` (482 lines)

`generate_report_pipeline(ticker, output_dir)`:

1. Creates per-run output directory: `output/{ticker}_{timestamp}/`
2. Generates charts in parallel (up to MAX_ATTEMPTS=3 retries per chart)
3. Runs validation on each chart
4. Generates analysis text with cross-referencing
5. Assembles final PDF report
6. Writes manifest.json with generation metadata

## Chart Agent

**File**: `agents/chart_agent.py` (1277 lines)

### Chart Types (CANONICAL_CHART_ORDER)

From `agents/chart_specs.py`:

1. `price_history` — Candlestick/OHLC chart
2. `volume_analysis` — Volume bars with moving average
3. `technical_indicators` — SMA overlays, RSI
4. `fundamental_metrics` — Revenue, earnings, margins
5. `growth_analysis` — QoQ and YoY growth rates
6. `sentiment_overview` — News sentiment timeline
7. `peer_comparison` — Multi-ticker comparison
8. `sec_financial_summary` — SEC filing data visualization

### Data Flow Per Chart

```
1. Fetch data    → 8 data fetcher functions (one per chart type)
2. Prep data     → chart_data_prep.py PREPARE_FUNCTIONS mapping
3. Validate      → chart_validation.py pre-render checks
4. Generate code → Cortex COMPLETE generates matplotlib code
5. Execute code  → subprocess.run() with 30s timeout
6. VLM critique  → vision_critique() evaluates the chart image
7. Refine        → Up to 2 iterations of VLM feedback + code regen
8. Final check   → Use fallback_code if refinement fails
```

### VLM Refinement Loop

```python
for iteration in range(MAX_VLM_ITERATIONS):  # MAX_VLM_ITERATIONS = 2
    # Generate chart code via Cortex COMPLETE
    code = generate_chart_code(chart_type, data, specs)

    # Execute in subprocess with timeout
    result = execute_chart_code(code, output_path, timeout=30)

    if result.success:
        # Get VLM critique
        critique = vision_critique(output_path, chart_type)

        if critique.passes:
            return output_path  # Chart accepted

        # Use critique feedback for next iteration
        feedback = critique.feedback
    else:
        # Code execution failed — try again with error context
        feedback = result.error

# All iterations exhausted — use fallback
return execute_fallback_code(chart_type, data, output_path)
```

### Fallback Code

Each chart type has a deterministic fallback (no LLM involved) that produces a basic but correct chart. This ensures the pipeline never fails completely.

### Data Fetchers

Each chart type has a dedicated data fetcher in `chart_agent.py`:

| Chart Type | Fetcher | Source Table |
|-----------|---------|-------------|
| price_history | `fetch_price_data()` | FCT_STOCK_METRICS |
| volume_analysis | `fetch_volume_data()` | FCT_STOCK_METRICS |
| technical_indicators | `fetch_technical_data()` | FCT_STOCK_METRICS |
| fundamental_metrics | `fetch_fundamental_data()` | FCT_FUNDAMENTALS_GROWTH |
| growth_analysis | `fetch_growth_data()` | FCT_FUNDAMENTALS_GROWTH |
| sentiment_overview | `fetch_sentiment_data()` | FCT_NEWS_SENTIMENT_AGG |
| peer_comparison | `fetch_peer_data()` | FCT_STOCK_METRICS (multi-ticker) |
| sec_financial_summary | `fetch_sec_data()` | FCT_SEC_FINANCIAL_SUMMARY |

## Validation Agent

**File**: `agents/validation_agent.py` (300 lines)

Two-tier validation:

### Tier 1: Rule-Based (Hard Pass/Fail)

- Image file exists and is non-empty
- Image dimensions meet minimum (e.g., 800x600)
- File is valid PNG/JPEG
- Chart has visible data (not blank)

### Tier 2: VLM Soft Pass

- `vision_critique()` evaluates chart quality
- Checks: labels visible, axes readable, data matches expectations
- Soft pass: logged as warning but doesn't block pipeline
- Runs up to 4 charts in parallel via ThreadPoolExecutor

## Analysis Agent

**File**: `agents/analysis_agent.py` (1290 lines)

### Chain-of-Analysis

Generates text analysis with cross-referencing between data sources:

1. **Technical Analysis** — Price trends, SMA crossovers, volume patterns
2. **Fundamental Analysis** — Revenue growth, margins, debt ratios
3. **Sentiment Analysis** — News sentiment trends, coverage volume
4. **SEC Filing Analysis** — Financial health from regulatory filings
5. **Cross-Reference** — Correlates signals across all domains

### Bedrock Integrations

| Integration | Purpose | Usage |
|------------|---------|-------|
| Bedrock Knowledge Base | RAG over SEC filings | `retrieve()`, `ask()`, `cross_ticker_analysis()` |
| Bedrock Guardrails | Content safety + grounding | Applied to all LLM outputs |
| Multi-Model Comparison | Consensus analysis | Compare outputs from multiple models |

### Cortex Functions

- `COMPLETE()` — Generates analysis text sections
- `SUMMARIZE()` — Condenses long SEC filing texts (< 40K chars)

### PEER_GROUPS Mapping

```python
PEER_GROUPS = {
    "AAPL": ["MSFT", "GOOGL"],
    "GOOGL": ["MSFT", "AAPL"],
    "JPM": [],  # Unique sector in tracked universe
    "MSFT": ["AAPL", "GOOGL"],
    "TSLA": [],  # Unique sector in tracked universe
}
```

## Report Agent

**File**: `agents/report_agent.py` (1855 lines)

### PDF Structure

1. Cover page with ticker, date, rating
2. Executive summary
3. Chart pages (8 charts with captions)
4. Detailed analysis sections
5. Signal summary table
6. Disclaimer page

### Design System (Midnight Teal)

| Element | Color |
|---------|-------|
| Primary | Midnight Teal (#004D4D) |
| Accent | Gold (#FFD700) |
| Background | Off-white (#F5F5F0) |
| Text | Dark gray (#333333) |

### Signal Derivation

The report agent derives a final **BUY / HOLD / SELL** rating from:

```
TREND_SIGNAL (weight 0.3)  + FUNDAMENTAL_SIGNAL (weight 0.3)
+ SENTIMENT_LABEL (weight 0.2) + FINANCIAL_HEALTH (weight 0.2)
```

### Output Manifest

`manifest.json` tracks all generated artifacts:

```json
{
  "ticker": "AAPL",
  "timestamp": "2024-01-15T10:30:00Z",
  "charts": ["price_history.png", "volume_analysis.png", ...],
  "report": "AAPL_report.pdf",
  "analysis_sections": 5,
  "quality_scores": {"chart_avg": 87, "analysis": 92},
  "pipeline_duration_seconds": 145
}
```

## Running the Pipeline

```python
from agents.orchestrator import generate_report_pipeline

# Single ticker
result = generate_report_pipeline("AAPL", output_dir="output/")

# With debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
result = generate_report_pipeline("TSLA", output_dir="output/")
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Empty chart | Missing data in analytics table | Run `dbt build` then check table has data for ticker |
| VLM timeout | Cortex COMPLETE slow response | Check Snowflake warehouse size, increase timeout |
| Subprocess error | Bad matplotlib code from LLM | Fallback code should activate; check fallback_code dict |
| Missing analysis section | Bedrock KB not accessible | Verify AWS credentials and KB ID |
| PDF layout broken | Too-long text in section | Check SUMMARIZE truncation |
