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

---

## Phase 6: Gemini Evaluation Fixes (2026-04-17)

### Context
Ran GOOGL FinSage report through Gemini as an external judge. Gemini identified systematic data quality issues across the report: Key Facts all N/A, peer comparisons broken, D/E ratios wildly wrong, revenue growth showing 0.0% for most quarters, and charts displaying misleading zeros instead of missing data. Root cause analysis revealed a mix of column name mismatches, data pipeline limitations, and anti-patterns in NULL handling. All fixes were designed to work across all 50 tracked tickers, not just GOOGL.

### 6.1 Key Facts All N/A — Column Name Mismatch
- **Problem**: Key Facts section (net margin, revenue, EPS) displayed all N/A values despite data existing in the warehouse.
- **Root Cause**: `analysis_agent.py` queried column `NET_MARGIN` but the actual column in `FCT_FUNDAMENTALS_GROWTH` is `NET_MARGIN_PCT`. The SQL error was silently swallowed by the except block, causing the entire key facts query to fail and return empty results.
- **Fix**: Changed 4 references from `NET_MARGIN` to `NET_MARGIN_PCT` in `analysis_agent.py` (lines ~912, 924, 1118, 1130).
- **Decision**: This was a silent failure — the except block caught the SQL compilation error and returned None without logging the SQL error itself. The column mismatch likely originated from a dbt model rename that wasn't propagated to the agent code.
- **Status**: Complete

### 6.2 Peer EPS/Revenue All N/A
- **Problem**: Peer comparison table showed N/A for all EPS and revenue values across all peer tickers.
- **Root Cause**: Same column name mismatch as 6.1 — the peer comparison query in `analysis_agent.py` also used `NET_MARGIN` instead of `NET_MARGIN_PCT`.
- **Fix**: Corrected alongside Fix 6.1.
- **Status**: Complete

### 6.3 Peer D/E Ratios Wildly Wrong (~100x Inflated)
- **Problem**: Peer D/E ratios showed values like 102.63 for AAPL (should be ~3.30). Target ticker GOOGL was correct because it had a special SEC override, but peers did not.
- **Root Cause**: Dual-source problem. `DIM_COMPANY.DEBT_TO_EQUITY` stores percentage-scaled values from Yahoo Finance (e.g., AAPL=102.63 meaning 102.63%, i.e., ratio of 1.03). `FCT_SEC_FINANCIAL_SUMMARY.DEBT_TO_EQUITY_RATIO` stores proper ratios (e.g., AAPL=3.30). The SEC D/E override in `analysis_agent.py` only applied to the target ticker, leaving peers with the ~100x-inflated DIM_COMPANY values.
- **Fix**: Batch SEC D/E override now queries `FCT_SEC_FINANCIAL_SUMMARY` for ALL tickers in the peer set and applies the override universally, not just for the target ticker.
- **Decision**: The proper fix is at the agent layer (override at query time) rather than changing the dbt model, because `DIM_COMPANY.DEBT_TO_EQUITY` is sourced directly from Yahoo Finance and other consumers may expect the original scale.
- **Status**: Complete

### 6.4 Revenue Growth 0.0% for Most Quarters
- **Problem**: Revenue growth chart showed 0.0% for 4 out of 5 quarters. Only the most recent quarter had a YoY growth value.
- **Root Cause**: Two compounding issues: (A) `fillna(0)` converted NULL growth values to literal 0.0%, making missing data look like zero growth. (B) yfinance `quarterly_income_stmt` returns only ~5 quarters of data, but the dbt model `fct_fundamentals_growth.sql` uses `LAG(revenue, 4)` which requires 8+ quarters to compute YoY growth. With only 5 quarters, only 1 quarter had a prior-year comparison.
- **Fix — Data Pipeline** (`src/data_loaders/fundamentals_loader.py`):
  - Added annual statement fetching (`yf_ticker.income_stmt`, `yf_ticker.balance_sheet`) alongside quarterly data
  - Added `seen_quarters` dedup set to prevent quarterly/annual overlap
  - Second pass derives quarterly approximations from annual data: `revenue/4`, `net_income/4`, `eps/4` (marked with `source: 'yahoo_finance_annual_approx'`)
  - Balance sheet items (total_assets, total_liabilities) taken as-is from annual data (point-in-time values don't need division)
  - Result: 16-21 quarters per ticker (up from 5-7)
- **Fix — Load Script** (`scripts/load_sample_fundamentals.py`):
  - Completely rewritten to use modular `FundamentalsLoader` instead of duplicate inline logic
  - Now loads all tickers from `config/tickers.yaml` (50 tickers) instead of 3 hardcoded tickers
- **Data Reload Results**:
  - All 50 tickers loaded successfully (0 failures)
  - `dbt build`: 35 PASS, 0 ERROR, 5 NO-OP exposures
  - GOOGL: 15 quarters in analytics, 11 with YoY growth (was 5 quarters, 1 with YoY)
  - All tickers: 15-17 quarters, 11-13 with YoY growth
- **Decision**: Annual-to-quarterly approximation (dividing by 4) is a known simplification — it doesn't capture seasonality. However, for YoY growth computation this is acceptable because: (a) we're comparing same-quarter-to-same-quarter, so the approximation bias cancels out, (b) the approximated rows are clearly marked with `source: 'yahoo_finance_annual_approx'` for transparency, (c) having approximate growth data is far better than showing 0.0% or N/A.
- **Status**: Complete

### 6.5 37 `fillna(0)` Anti-Patterns Across Charts
- **Problem**: Charts displayed misleading zeros where data was actually missing. Revenue growth of 0.0%, EPS of 0.0, sentiment scores of 0 — all indistinguishable from actual zero values.
- **Root Cause**: 37 occurrences of `fillna(0)` across `chart_data_prep.py` (16) and `chart_agent.py` (21) silently converted NaN/NULL to zero before charting.
- **Fix** (`agents/chart_data_prep.py`):
  - All 16 `fillna(0)` calls removed
  - Added `_safe_round_list()` helper that preserves `None` for NaN entries while rounding valid float values
  - All data preparation methods now return `None` for missing data points instead of `0`
- **Fix** (`agents/chart_agent.py`):
  - 20 of 21 `fillna(0)` calls removed from fallback chart code templates
  - Chart fallback code rewritten to filter `None`/`NaN` before plotting and show "N/A" annotations for missing quarters
- **Decision**: Preserving `None` over `fillna(0)` is the correct approach because: (a) matplotlib handles `None` gracefully (gaps in line charts, missing bars), (b) analysts need to distinguish "no data" from "zero value", (c) downstream LLM analysis is more accurate when it sees gaps rather than artificial zeros.
- **Status**: Complete

### 6.6 SEC Risk Factors Generic Summarization
- **Problem**: SEC Risk Factors section produced generic, boilerplate-sounding summaries that didn't surface company-specific risks.
- **Root Cause**: Cortex SUMMARIZE produces generic summaries from risk factor text. The underlying data is fine — `RAW_SEC_FILING_DOCUMENTS.RISK_FACTORS_TEXT` contains 113K-146K chars of detailed risk text per filing. The issue is the summarization model's tendency to generalize rather than extract specific risks.
- **Decision**: Deferred. This is a Cortex model quality issue, not a data engineering problem. Potential future fixes: (a) use Cortex COMPLETE with a more specific prompt instead of SUMMARIZE, (b) pre-chunk the risk factors and summarize each category separately, (c) use Bedrock KB RAG to retrieve specific risk passages.
- **Status**: Deferred

### Summary Table

| # | Issue | Root Cause | Files Modified | Impact |
|---|-------|-----------|---------------|--------|
| 6.1 | Key Facts all N/A | `NET_MARGIN` vs `NET_MARGIN_PCT` column mismatch | `analysis_agent.py` | All tickers |
| 6.2 | Peer data all N/A | Same column mismatch in peer query | `analysis_agent.py` | All tickers |
| 6.3 | Peer D/E ~100x wrong | SEC D/E override only for target ticker | `analysis_agent.py` | All tickers |
| 6.4 | Revenue Growth 0.0% | Only 5 quarters (need 8+ for YoY) + `fillna(0)` | `fundamentals_loader.py`, `load_sample_fundamentals.py` | All 50 tickers |
| 6.5 | Charts show 0 not N/A | 37 `fillna(0)` calls | `chart_data_prep.py`, `chart_agent.py` | All charts, all tickers |
| 6.6 | Generic risk factors | Cortex SUMMARIZE quality | — | Deferred |

---

## Phase 7: LLM-as-Judge Data Accuracy Fixes (2026-04-17)

### Context
Ran NFLX FinSage report through an LLM-as-Judge evaluation that scored the report 6.5/10 overall, with Data Accuracy as the weakest dimension at 5/10. The judge flagged a 69.7% net margin (should be ~25%), a D/E ratio of 63.78 (should be ~0.64), and other data inconsistencies. Root cause analysis traced the net margin error to the SEC XBRL deduplication logic in the dbt transformation layer, and the D/E error to Yahoo Finance storing values as percentages rather than ratios. A 7-step fix was designed and executed. All fixes are ticker-agnostic — they apply to all tickers, not just NFLX.

### 7.1 SEC XBRL Deduplication — Root Cause of 69.7% Net Margin
- **Problem**: NFLX Q3 2025 net margin showed 69.7% in the report (should be ~25.8%).
- **Root Cause**: `fct_sec_financial_summary.sql` dedup logic used `ABS(value) ASC` ordering for income statement items, intending to pick the "smallest absolute value" as the correct one. But 10-Q filings include prior-year comparison figures tagged with the current `fiscal_year` but with a prior-year `period_end` date. The old logic mixed current-period and prior-year rows, selecting a prior-year net income ($2.37B) against current-period revenue ($10.25B), producing a wildly wrong margin.
- **Key Insight**: `YEAR(period_end) = fiscal_year` reliably identifies current-period rows, because prior-year comparison values have `period_end` in the prior year while sharing the current `fiscal_year`.
- **Fix**: Replaced the dedup strategy in `fct_sec_financial_summary.sql` (lines 29-53). New two-CTE approach: (1) `current_period` CTE filters `WHERE YEAR(period_end) = fiscal_year` to exclude prior-year comparison rows; (2) `deduped` CTE applies `ROW_NUMBER() OVER (PARTITION BY ticker, cik, concept, fiscal_year, fiscal_period ORDER BY period_end DESC, filed_date DESC)` among remaining rows.
- **Verification**: `dbt run` SUCCESS (2/2), `dbt test` PASS (5/5). NFLX Q3 2025 net_margin_pct: 25.84% (was 69.65%). FY 2025: 24.30%.
- **Side Effect**: 2024/2023 quarterly rows now have NULL revenue/income because only prior-year comparison data existed for those periods in the raw XBRL data. This is a pre-existing data ingestion limitation (SEC filing coverage), not a regression from the fix.
- **Status**: Complete

### 7.2 Yahoo Finance D/E Percentage-to-Ratio Normalization
- **Problem**: `DIM_COMPANY.DEBT_TO_EQUITY` showed 63.782 for NFLX instead of 0.6378.
- **Root Cause**: Yahoo Finance reports D/E as a percentage (63.782 = 63.782%), but the column was stored as-is without normalization. This contradicted `FCT_SEC_FINANCIAL_SUMMARY.DEBT_TO_EQUITY_RATIO` which stores proper ratios.
- **Fix**: Changed `dim_company.sql` line 71 from `f.debt_to_equity,` to `ROUND(f.debt_to_equity / 100, 4) AS debt_to_equity,`.
- **Verification**: `dbt run` SUCCESS. NFLX D/E now 0.6378 (was 63.782). All tickers normalized.
- **Decision**: Fixed at the dbt layer (unlike Phase 6 Fix 6.3 which fixed at the agent layer). Phase 6's agent-level override for peers is now complementary — the dbt fix ensures `DIM_COMPANY` always has correct values, while the agent clamp (Fix 7.3) provides defense-in-depth.
- **Status**: Complete

### 7.3 D/E Outlier Clamp in Peer Comparison
- **Problem**: If the SEC D/E override in `generate_peer_comparison()` fails silently (e.g., no SEC data for a peer), raw Yahoo values could still leak through despite Fix 7.2.
- **Fix**: Added 7-line clamp after the SEC override try/except in `analysis_agent.py` (after line 1174). Iterates all tickers in `company_map`; any `debt_to_equity` with `abs(value) > 20` is set to `None` with a warning log.
- **Decision**: Defense-in-depth pattern. Fix 7.2 corrects the source; Fix 7.3 catches any remaining outliers at the consumer. The ±20 threshold is generous enough for highly-leveraged companies (e.g., banks) while catching obviously wrong percentage-scale values.
- **Status**: Complete

### 7.4 Key Facts Backfill — Wrong Chart Data Keys
- **Problem**: Key Facts in the Executive Summary showed N/A for revenue, EPS, and net income even when chart data had valid values.
- **Root Cause**: `report_agent.py` backfill logic used non-existent keys (`latest_revenue`, `latest_net_income`, `latest_quarter`) to look up chart `data_summary` values. The actual keys are `total_revenue` (from `financial_health` chart), `latest_eps` (from `eps_trend` chart).
- **Fix**: Rewrote backfill block at `report_agent.py` lines 1156-1173. Now correctly maps: `financial_health.total_revenue` → `facts["revenue"]`, `eps_trend.latest_eps` → `facts["eps"]`, and derives net_income as `revenue × net_margin_pct / 100` when both are available.
- **Status**: Complete

### 7.5 TOC Page Number Drift — Pass 1/Pass 2 Template Mismatch
- **Problem**: TOC page numbers could be wrong if Pass 1 (page number discovery) and Pass 2 (final render) produced different pagination.
- **Root Cause**: Pass 1 used bare `PageTemplate` objects without `onPage` callbacks, while Pass 2 used `onPage=draw_cover_bg` and `onPage=draw_content_page`. These callbacks add header/footer elements that can affect content frame available height and thus page breaks.
- **Fix**: (A) Added identical `onPage` callbacks to Pass 1 templates at `report_agent.py` lines 2047-2052, matching Pass 2. (B) Added drift validation at lines 2058-2071: snapshots `pass1_pages = dict(page_map)` before Pass 2, then compares against Pass 2's `page_map` after build, logging warnings for any section with mismatched page numbers.
- **Verification**: End-to-end run showed no TOC drift warnings.
- **Status**: Complete

### 7.6 Cross-Field Consistency Validation
- **Problem**: No pre-assembly checks existed to catch data inconsistencies before they rendered into the final PDF. Issues like the 69.7% margin could have been flagged before the report was generated.
- **Fix**: Added `_validate_report_data()` function at `report_agent.py` line 106 (93 lines). Performs 5 non-blocking checks that log warnings but never raise:
  1. **Net margin consistency**: Compares SEC-derived `net_margin_pct` (from `financial_health` chart) vs Yahoo `profit_margin` (from `key_facts`). Normalizes Yahoo decimal→pct if needed. Warns if difference > 5 percentage points.
  2. **D/E ratio sanity**: Flags negative D/E or values > 20 from either SEC or Yahoo source.
  3. **Stock price sanity**: Flags prices ≤ 0 or > $100,000.
  4. **N/A audit**: Lists which Executive Summary metrics will render as "N/A" (price, margin, D/E, EPS, revenue growth).
  5. **EPS/revenue directional check**: Warns if EPS is negative while revenue is positive (suggests net income data issue).
- **Call site**: Invoked at `report_agent.py` line 1924, after analysis_map is built but before PDF assembly begins.
- **Verification**: During end-to-end run, correctly caught: `[NFLX] Net margin mismatch: SEC=25.80% vs Yahoo=20.07% (diff 5.73 pp) — PDF will use SEC value`. This is expected — SEC reports Q3 quarterly margin while Yahoo reports trailing-12-month margin.
- **Decision**: Non-blocking by design. The report always renders; the build log captures every data-quality concern for post-hoc review. This pattern avoids brittle validation that blocks report generation for minor discrepancies.
- **Status**: Complete

### 7.7 End-to-End Verification
- **Scope**: Full pipeline re-run (`dbt run` + `dbt test` + `python agents/orchestrator.py --ticker NFLX`) to verify all 6 fixes work together.
- **Results**:
  - `dbt run`: 2/2 models SUCCESS
  - `dbt test`: 5/5 PASS
  - Pipeline: Completed in 315s (5.3 min), 8 charts generated
  - PDF: `NFLX_FinSage_Report_20260417_174249.pdf` (1050.3 KB, ~20 pages)
  - `financial_health` chart `data_summary`: `net_margin_pct=25.8` (was 69.65%), `debt_to_equity_ratio=1.12`, `total_revenue=$33.1B`
  - Validation function caught net margin mismatch (5.73pp SEC vs Yahoo — expected, different time windows)
  - No TOC drift detected
  - One chart rendering retry (`revenue_growth` iter2 tick label mismatch) — auto-recovered with simplified prompt
- **Status**: Complete

### Summary Table

| # | Issue | Root Cause | Files Modified | Impact |
|---|-------|-----------|---------------|--------|
| 7.1 | Net margin 69.7% (should be ~25%) | XBRL dedup mixed current + prior-year rows | `fct_sec_financial_summary.sql` | All tickers |
| 7.2 | D/E ratio ~100x inflated | Yahoo Finance stores D/E as percentage | `dim_company.sql` | All tickers |
| 7.3 | D/E outliers in peer table | No clamp after SEC override failure | `analysis_agent.py` | All tickers |
| 7.4 | Key Facts all N/A | Wrong chart data_summary key names | `report_agent.py` | All tickers |
| 7.5 | TOC page numbers could drift | Pass 1 missing onPage callbacks | `report_agent.py` | All reports |
| 7.6 | No pre-assembly data checks | Missing validation function | `report_agent.py` | All tickers |
| 7.7 | End-to-end verification | — | — | NFLX verified |
