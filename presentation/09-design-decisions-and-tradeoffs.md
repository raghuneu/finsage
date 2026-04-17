# Design Decisions & Trade-offs — Q&A Preparation

## Purpose

This document prepares you for the hardest questions in your presentation. Each entry follows the format: **Question → Answer → Trade-off acknowledged → Alternative considered**.

---

## Architecture-Level Decisions

### 1. Why a multi-agent pipeline instead of a single monolithic script?

**Answer:** Each agent has a distinct responsibility and failure mode. Chart generation (GPU-bound matplotlib) fails differently from LLM analysis (API timeouts) and PDF assembly (layout errors). Separating them enables:
- Retry logic at each stage (re-render failed charts without re-running analysis)
- The `--skip-charts` flag reuses previous charts for faster iteration
- Independent testing of each agent

**Trade-off:** More code complexity (4 files + orchestrator vs 1 file). State passing between agents adds coordination overhead.

**Alternative considered:** LangChain/CrewAI agent framework. Rejected because the CAVM flow is linear (not dynamic agent routing), making a framework overkill.

---

### 2. Why Snowflake + AWS Bedrock instead of a single cloud?

**Answer:** Each platform provides unique capabilities:
- **Snowflake Cortex**: LLM/VLM accessible via SQL, data never leaves the warehouse, zero API key management
- **Bedrock KB**: Managed RAG with auto-indexing from S3 — no vector DB to operate
- **Bedrock Guardrails**: Financial compliance (block investment advice, redact PII) — Cortex has no equivalent
- **Bedrock Multi-Model**: Access to Llama, Titan, Mistral, Claude in one API — Cortex only offers specific models

**Trade-off:** Two sets of credentials, two billing accounts, network latency between platforms.

**Alternative considered:** All-Snowflake (Cortex Search for RAG). Cortex Search existed but lacked the guardrails and multi-model capabilities at the time.

---

### 3. Why a three-layer warehouse (RAW → STAGING → ANALYTICS)?

**Answer:** The medallion architecture provides:
- **RAW**: Immutable source of truth with lineage (`source`, `ingested_at`)
- **STAGING**: Data cleaning without modifying source (filter invalid, compute `daily_return`)
- **ANALYTICS**: Business-ready tables with derived signals consumed by agents and frontend

**Trade-off:** Storage cost for analytics tables (duplicates staging data). More dbt models to maintain.

**Alternative considered:** Two layers (RAW → ANALYTICS). Rejected because mixing cleaning and business logic in one layer makes debugging data issues harder.

---

### 4. Why dbt for transformations instead of Python/Snowpark?

**Answer:** dbt provides:
- SQL-native transformations (the warehouse team thinks in SQL)
- Built-in testing (`not_null`, `unique`, `accepted_values`)
- Automatic documentation and lineage
- Staging views = zero storage cost, always fresh

**Trade-off:** dbt is SQL-only; complex transformations require Jinja templating. Debugging compiled SQL is harder than Python.

**Alternative considered:** Snowpark DataFrames in Python. Would have kept everything in one language but loses dbt's testing and documentation ecosystem.

---

### 5. Why Next.js + FastAPI instead of pure Streamlit?

**Answer:** The original Streamlit frontend (`frontend/app.py`) worked for prototyping but had limitations:
- No real-time chart library (lightweight-charts for financial OHLCV data)
- Limited control over layout and theming
- Poor mobile responsiveness
- Synchronous execution model doesn't support background CAVM pipeline

The React frontend provides: full MUI component library, async pipeline polling, editorial design system, and TradingView-grade charts.

**Trade-off:** Two languages (TypeScript + Python), two servers (port 3000 + 8000), more setup complexity.

**Alternative considered:** Streamlit with custom components. Rejected because custom Streamlit components require JavaScript anyway, and the result would be less maintainable.

---

## Data Pipeline Decisions

### 6. Why MERGE instead of INSERT for data loading?

**Answer:** MERGE provides idempotency. Re-running the pipeline for the same date doesn't create duplicates. This is critical when:
- API calls return overlapping date ranges
- Airflow retries a failed task that partially succeeded
- Manual re-runs during development

**Trade-off:** MERGE is slightly slower than INSERT for new data (matching check). Requires well-defined merge keys.

**Alternative considered:** DELETE + INSERT (truncate-and-reload). Simpler but loses historical records during the brief window between delete and insert.

---

### 7. Why incremental loading instead of full reload?

**Answer:** API rate limits make full reloads impractical:
- Alpha Vantage free tier: 5 calls/minute
- NewsAPI: 100 calls/day
- SEC EDGAR: 10 requests/second (with User-Agent requirement)

Incremental loading (`get_last_loaded_date()`) fetches only new data, reducing API calls by 90%+.

**Trade-off:** Cannot detect retroactive data corrections by the source (e.g., Yahoo Finance restating historical prices). Requires a separate "full refresh" path for data quality issues.

---

### 8. Why quality scoring instead of rejecting bad records?

**Answer:** Low-quality records are preserved with their score, not discarded. This enables:
- Downstream filtering by quality threshold
- Debugging data issues (inspect the low-quality records)
- Analytics on data quality trends over time

**Trade-off:** More storage for low-quality records. Downstream consumers must actively filter.

**Alternative considered:** Hard validation (reject on failure). Too aggressive — some valid records might fail edge-case validation rules.

---

## AI & Analysis Decisions

### 9. Why VLM refinement for charts instead of template-based generation?

**Answer:** LLM-generated matplotlib code frequently has visual bugs:
- Overlapping labels
- Wrong colors or missing legends
- Cut-off titles
- Incorrect axis scaling

The VLM refinement loop catches these by **actually seeing the rendered image** and feeding specific feedback back to the LLM. This is the same review cycle a human designer would do.

**Trade-off:** 2× the Cortex API calls per chart (2 text LLM + 1 VLM = 3 calls per chart × 8 charts = 24 Cortex calls). Adds ~5 minutes to pipeline runtime.

**Alternative considered:** Static matplotlib templates with data insertion. Would be faster and deterministic but loses the ability to adapt chart styling to different data distributions.

---

### 10. Why Chain-of-Analysis (serial) instead of parallel chart analysis?

**Answer:** Parallel analysis produces disconnected bullet points. Serial analysis produces a narrative:
- Chart 5 (financial health) can say "consistent with the bullish price trend observed earlier"
- Chart 8 (sentiment) can say "in contrast to the declining margins, market sentiment remains positive"

This mimics how a human analyst would write a report — building a story, not listing facts.

**Trade-off:** Serial processing adds ~3 minutes vs parallel. The pipeline is 5-15 minutes total, so this is acceptable.

---

### 11. Why fallback chains everywhere instead of failing fast?

**Answer:** Financial report generation is user-initiated and takes 5-15 minutes. Failing at minute 12 because a VLM model returned a timeout would waste the user's time. Every component has fallbacks:

| Component | Primary | Fallback 1 | Fallback 2 |
|-----------|---------|------------|------------|
| Chart code | LLM-generated | Fallback code (hardcoded) | N/A |
| VLM critique | claude-sonnet-4-6 | pixtral-large | Text-only critique |
| KB RAG | Bedrock retrieve | Skip SEC context | N/A |
| Guardrails | check_output() | Include text without validation | N/A |
| Multi-model | 3-model consensus | Single Cortex call | N/A |
| VLM validation | VLM score check | Soft pass (include anyway) | N/A |

**Trade-off:** Reports may include unvalidated content when fallbacks activate. The appendix notes which components were used.

---

### 12. Why post-hoc guardrails instead of guarded generation?

**Answer:** Text is generated by Snowflake Cortex, not Bedrock. Applying guardrails during generation would require:
1. Switching to a Bedrock model (adding latency)
2. Sending data outside Snowflake (losing data locality)
3. Paying for both generation and guardrail inference

The `apply_guardrail()` API validates existing text without a model call — fast, cheap, and keeps generation inside Snowflake.

**Trade-off:** Guardrails can only reject/modify text after generation. If the LLM generates inappropriate content, the compute for generation is wasted.

---

## Frontend Decisions

### 13. Why a separate FastAPI backend instead of Next.js API routes?

**Answer:** The entire data stack is Python: Snowpark, data loaders, CAVM agents, Bedrock SDK (boto3). Keeping the API in Python means:
- Direct import of existing code (`scripts/snowflake_connection.py`, `agents/`, `document_agent.py`)
- No Python-in-Node bridges (pyodide, etc.)
- The data team can contribute to the API without learning TypeScript

**Trade-off:** Two servers (port 3000 + 8000), CORS configuration required, more deployment complexity.

---

### 14. Why polling for CAVM status instead of WebSockets?

**Answer:** The CAVM pipeline takes 5-15 minutes. Polling every 5 seconds is:
- Simpler to implement (no WebSocket connection management)
- More resilient (lost connections auto-recover on next poll)
- Sufficient for the UX (users don't need sub-second updates for a 10-minute pipeline)

**Trade-off:** 60-180 redundant HTTP requests during a pipeline run. Negligible overhead compared to the pipeline itself.

---

### 15. Why the "Fancy Flirt" editorial design instead of a standard dashboard theme?

**Answer:** Financial research reports have a specific aesthetic — serif headings, warm tones, premium feel. The editorial design:
- Differentiates from generic blue-on-white data dashboards
- Matches the Midnight Teal PDF report branding
- Creates visual continuity between the web interface and generated PDFs

**Trade-off:** Non-standard color choices may require explanation. The warm palette is less conventional for data visualization.

---

## Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| SQL injection risk in FastAPI queries (f-string interpolation) | Input sanitized via uppercase + strip + max_length, but not parameterized | Should use Snowpark parameterized queries for production |
| In-memory task store for CAVM/pipeline status | Status lost on API restart | Production: use Redis or database-backed task store |
| Single-threaded Snowflake sessions in concurrent code | Agents use separate sessions, but race conditions possible | Thread-local sessions or connection pooling |
| No authentication on the frontend | Anyone with network access can trigger pipelines | Production: add auth (NextAuth, OAuth) |
| 50-ticker limit in tickers.yaml | Hard-coded batch size assumptions | Make batch size dynamic based on ticker count |
| VLM refinement adds 5+ minutes | Pipeline is 5-15 min total | `--skip-charts` flag for iteration; worth it for quality |

---

## What We Would Do Differently

1. **Use Snowpark parameterized queries** instead of f-string SQL for all API endpoints
2. **Add Redis-backed task queue** (Celery or RQ) instead of in-memory dict for async jobs
3. **Implement authentication** (OAuth2 or API keys) for the FastAPI backend
4. **Add circuit breakers** for external API calls (currently retry-only)
5. **Use Snowflake Cortex Search** for RAG (once it supports document-level metadata filtering)
6. **Add data lineage tracking** with OpenLineage integration in Airflow

---

*Previous: [08-infrastructure-architecture.md](./08-infrastructure-architecture.md) | Next: [10-talking-points.md](./10-talking-points.md)*
