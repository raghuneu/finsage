# FinSage Project Retrospective

Tracking key decisions, changes, and rationale for improvements inspired by ChineseFinSight (AFAC2025 1st place).

---

## 2026-04-14: Initial Gap Analysis

### Context
Compared FinSage (16-page PDF, CAVM pipeline) against ChineseFinSight (49-page reports, CAVM architecture with code execution agents, 50+ tools). Goal: identify what ChineseFinSight does better and bring those improvements to FinSage while keeping our Snowflake+Bedrock stack.

### Key Findings
- FinSage **exceeds** ChineseFinSight in: SEC filing integration (Bedrock KB RAG), multi-model consensus, content safety guardrails, peer comparison, news sentiment analysis
- FinSage **lags** in: report depth (16 vs 49 pages), financial deep dive sections, valuation models, citation system, dynamic task generation, cover page financial tables
- **4 bugs found** in generated PDF: epoch dates on sentiment chart, "None" operating margin, truncated business segments, HTML entity rendering

### Decisions Made
1. Prioritize bug fixes first (Phase 1) before adding new features
2. Add 4 new report sections inspired by ChineseFinSight's outline template: Financial Deep Dive, Valuation, Ownership, expanded Company Overview
3. Keep Snowflake+Bedrock stack (not migrate to OpenAI-compatible like ChineseFinSight)
4. Target 25-30 page reports (up from 16) without bloat
5. Add citation system and polish pass for professional quality

---

## Phase 1: Bug Fixes

### 1.1 Sentiment Chart Epoch Dates
- **Problem**: X-axis shows 1969-1970 dates instead of 2026 dates
- **Root Cause**: CSV round-trip date loss. `execute_chart_code()` writes DataFrame to CSV, subprocess reads it back with `pd.read_csv()`. Datetime columns lose their type and become strings/numbers. LLM-generated code doesn't re-parse them, so matplotlib shows epoch values.
- **Fix**: Added auto-date-conversion loop in the runner script template (`chart_agent.py:349-364`). Runs after `pd.read_csv()` and before LLM code. Detects columns with 'date'/'DATE'/'Date', tries `pd.to_datetime()` standard parsing, falls back to epoch unit parsing (ms or s) if all NaT.
- **Status**: Complete

### 1.2 Operating Margin "None"
- **Problem**: Financial Health table displays "Operating Margin Pct: None"
- **Root Cause**: `fetch_sec_financial_summary()` set `result["operating_margin_pct"] = None` as placeholder but never computed it. SEC table has `operating_income`, fundamentals has `revenue`, but the cross-computation was missing.
- **Fix**: (A) Added computation in `chart_agent.py:191-196` — takes SEC `operating_income` / fundamentals `revenue` when both are available, rounds to 1 decimal. (B) Added None filter in `report_agent.py:823-824` — `build_chart_section()` now skips key-value pairs where value is None.
- **Status**: Complete

### 1.3 Truncated Business Segments
- **Problem**: Text cut off mid-sentence ("a news and magaz")
- **Root Cause**: `generate_company_overview()` in `analysis_agent.py` truncated each KB chunk to 300 chars (`c["text"][:300]`) and only used 2 chunks, causing mid-sentence cuts.
- **Fix**: Now retrieves full text from up to 3 KB chunks, sends them to Cortex for synthesis into a clean 2-3 sentence summary with revenue breakdown. Falls back to 600-char truncation only if Cortex fails. (`analysis_agent.py:722-735`)
- **Decision**: Using LLM synthesis instead of raw concatenation ensures grammatically complete sentences and better information density.
- **Status**: Complete

### 1.4 HTML Entity Rendering
- **Problem**: "S&P; 500" instead of "S&P 500"
- **Root Cause**: `clean_llm_text()` in `report_agent.py` stripped markdown but didn't decode HTML entities. LLMs sometimes emit `&amp;`, `&lt;`, etc.
- **Fix**: Added `import html` and `html.unescape()` call at end of `clean_llm_text()` (`report_agent.py:138,149`).
- **Status**: Complete

---

## Phase 2: Deepen Report Content

### 2.5 Financial Deep Dive Section
- **Goal**: Add quarterly income statement trends and balance sheet commentary (inspired by ChineseFinSight's 8-page financial analysis)
- **Implementation**: New `generate_financial_deep_dive()` in `analysis_agent.py` queries `FCT_SEC_FINANCIAL_SUMMARY` for up to 8 quarters. Formats revenue, net income, operating income, EPS, cash into a structured table. Uses Cortex for narrative trend analysis and balance sheet commentary.
- **PDF**: New `build_financial_deep_dive()` in `report_agent.py` renders Income Statement Trends table, Balance Sheet Summary table, narrative analysis paragraph, and balance sheet commentary.
- **Status**: Complete

### 2.6 Valuation Analysis Section
- **Goal**: Add relative valuation comparison against peers
- **Implementation**: New `generate_valuation_analysis()` in `analysis_agent.py` queries `DIM_COMPANY` for target ticker and `PEER_GROUPS` peers. Pulls P/E ratio, profit margin, debt-to-equity, market cap. Uses Cortex for relative valuation narrative.
- **PDF**: New `build_valuation_section()` in `report_agent.py` renders peer comparison table with target ticker highlighted (green background `#e6f7f2`) and valuation narrative.
- **Status**: Complete

### 2.7 Ownership/Institutional Holdings
- **Decision**: SKIPPED. Checked Snowflake tables — no ownership or institutional holdings data exists in any schema. Would require a new data source (e.g., SEC 13F filings or Bloomberg Terminal) which is out of scope for current infrastructure.
- **Status**: Skipped (no data)

### 2.8 Enhanced Company Overview
- **Goal**: Expand from generic 4-5 sentences to institutional-grade overview with TAM, competitive advantages, and competitive landscape
- **Implementation**: Updated `generate_company_overview()` prompt in `analysis_agent.py` to request 6-8 sentences covering TAM, competitive advantages, and growth drivers. Added new competitive landscape generation using `PEER_GROUPS` context (3-4 sentences on relative market position, differentiators, threats).
- **PDF**: Added "Competitive Landscape" sub-section in `build_company_overview()` with header and divider.
- **Status**: Complete

---

## Phase 3: Analysis Quality

### 3.9 Strengthen Chain-of-Analysis Cross-References
- **Problem**: Prior analysis context truncated to 250 chars each, losing important findings. Cross-reference prompt was vague ("where appropriate").
- **Fix**: Doubled context window from 250 to 500 chars per prior analysis. Made cross-reference directive mandatory ("you MUST cross-reference at least one prior finding") with specific instructions: reference by name, identify confirms/contradicts/nuances, use connective phrases, call out divergences as risks or opportunities.
- **Decision**: Mandatory cross-references over optional produces a more coherent report narrative where sections build on each other.
- **Status**: Complete

### 3.10 Professional Tone Polish Pass
- **Problem**: All 6 chart prompts requested "3-4 sentence analysis" producing thin output. Prompts lacked specific analytical guidance per chart type.
- **Fix**: Upgraded all `CHART_PROMPTS` to request "4-6 sentence analysis" with numbered analytical requirements specific to each chart type (e.g., SMA alignment analysis for price, margin expansion/compression for revenue growth). Added "Avoid generic statements — every sentence must add analytical value" directive. Changed system role from "professional financial report" to "institutional-grade financial report".
- **Investment thesis**: Upgraded from "4-6 sentences" to "6-8 sentences" with explicit bull/bear case structure, contradiction identification, and conviction level (high/moderate/low).
- **Status**: Complete

### 3.11 Citation/Footnote System
- **Goal**: Add data source transparency and methodology documentation (inspired by ChineseFinSight's source attribution)
- **Implementation**: Added "Methodology Notes & Citations" table in the Appendix of `report_agent.py`. Maps each of 9 report sections to its data source and analytical methodology (e.g., "30-day rolling volatility calculated as annualized standard deviation of daily returns").
- **Decision**: Chose a structured table over inline footnotes — cleaner with reportlab's flowable model and matches professional equity research format where methodology notes appear in the appendix.
- **Status**: Complete

---

## Phase 4: Chart Variety

### 4.12 New Chart Types
- **Goal**: Expand from 6 to 8 chart types using existing SEC data
- **Charts added**:
  1. `margin_trend` — Net margin and operating margin trend over fiscal periods (line chart with area fill). Data source: `FCT_SEC_FINANCIAL_SUMMARY` (net_margin, operating_margin columns).
  2. `balance_sheet` — Total assets vs total liabilities vs stockholders' equity (stacked bar with line overlay). Data source: `FCT_SEC_FINANCIAL_SUMMARY` (total_assets, total_liabilities, stockholders_equity columns).
- **Decision**: Chose margin_trend and balance_sheet over segment revenue or cash flow because: (a) the SEC data already has the required columns, (b) these chart types provide the most analytical value by visualizing trends that were previously only in text, (c) a radar/spider chart would require arbitrary normalization which reduces analytical rigor.
- **Files modified**: `chart_agent.py` (summary builders, CHART_DEFINITIONS, chart_data_map, data_fetchers), `analysis_agent.py` (ANALYSIS_ORDER, KB_QUERIES, CHART_PROMPTS)
- **Status**: Complete

### 4.13 Dynamic Chart Selection
- **Goal**: Intelligent chart selection based on data quality
- **Implementation**: Added `MIN_ROWS` threshold map in `generate_charts()`. Charts like `margin_trend` and `balance_sheet` require at least 3 data rows to be meaningful (a trend needs 3+ points). Charts with insufficient data are skipped with a warning log.
- **Decision**: Lightweight data-quality gating over full LLM-based chart suggestion. The LLM approach would add latency and cost for marginal benefit given our fixed data sources.
- **Status**: Complete

---

## Phase 5: Model Upgrades

### 5.1 Cortex Model Audit & Upgrade
- **Problem**: Pipeline was using older models (`mistral-large` for analysis, `llama3.1-70b` for chart code gen) while significantly superior models were available on the SFEDU02 account. The 60s timeout on Cortex LLM calls was too tight, causing chart generation to fail with "Cortex LLM call timed out after 60s".
- **Audit**: Probed all models via `SNOWFLAKE.CORTEX.COMPLETE()`. Confirmed availability of: `claude-4-sonnet`, `claude-3-7-sonnet`, `llama4-maverick`, `llama4-scout`, `llama3.1-405b`, `mistral-large2`, `deepseek-r1`, `snowflake-llama-3.3-70b`, `llama3.3-70b`. Models NOT available: `claude-3.5-sonnet`, `llama3.2-90b`. Deprecated: `jamba-1.5-large`.
- **Changes**:
  - `analysis_agent.py` CORTEX_MODEL: `mistral-large` → `mistral-large2` (direct successor, better instruction following)
  - `chart_agent.py` CORTEX_MODEL_LLM: `llama3.1-70b` → `llama4-maverick` (Llama 4, significantly better code generation)
  - `vision_utils.py` cortex_complete default: `mistral-large` → `mistral-large2` (aligns with analysis agent)
  - `chart_agent.py` VLM_CALL_TIMEOUT_SEC: `60` → `90` (prevents timeout failures)
- **Decision**: Chose `mistral-large2` over `claude-4-sonnet` for analysis because FinSage makes ~15-20 Cortex calls per report — Claude would be 3-5x more expensive per call for marginal quality gain. Chose `llama4-maverick` over `llama3.1-405b` for chart code gen because Maverick is both faster and better at code generation despite being smaller. Kept `pixtral-large` for VLM fallback behind `openai-gpt-5.2` (primary), both via Snowflake Cortex.
- **Also fixed**: Pandas FutureWarning at `chart_agent.py:168` — `dim_df.iloc[0][0]` → `dim_df.iloc[0, 0]` (deprecated Series positional indexing).
- **Status**: Complete

### 5.2 Upgrade to claude-opus-4-6
- **Problem**: User requested upgrading the primary LLM from `mistral-large2` / `llama4-maverick` to `claude-opus-4-6` for maximum analysis quality across the entire pipeline.
- **Verification**: Probed `claude-opus-4-6` via `SNOWFLAKE.CORTEX.COMPLETE()` — confirmed available on SFEDU02 account.
- **Changes**:
  - `analysis_agent.py` CORTEX_MODEL: `mistral-large2` → `claude-opus-4-6` (9 LLM calls per report)
  - `chart_agent.py` CORTEX_MODEL_LLM: `llama4-maverick` → `claude-opus-4-6` (chart code generation)
  - `vision_utils.py` cortex_complete default: `mistral-large2` → `claude-opus-4-6` (shared utility)
  - `chart_agent.py` VLM_CALL_TIMEOUT_SEC: `90` → `120` (claude-opus is slower, needs more headroom)
  - `scripts/sec_filings/document_agent.py` default: `llama3.1-70b` → `claude-opus-4-6`
  - `report_agent.py`: Updated 4 hardcoded model name strings in methodology/appendix text
  - `frontend/pages/10_System_Status.py`: Updated health check probe to use `claude-opus-4-6`
- **Tradeoff**: `claude-opus-4-6` is significantly more expensive and slower than `mistral-large2`, but produces the highest quality analysis text. With ~25+ Cortex calls per report, generation time and cost will increase. User accepted this tradeoff for quality.
- **Kept unchanged**: `pixtral-large` for VLM fallback (specialized vision model), `openai-gpt-5.2` for primary VLM critique (via Snowflake Cortex).
- **Status**: Complete
