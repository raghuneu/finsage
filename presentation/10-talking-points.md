# Presentation Talking Points & Demo Guide

## Suggested Presentation Flow (15-20 Minutes)

### Opening (2 minutes)

**Slide 1: What is FinSage?**
> "FinSage is an end-to-end financial intelligence platform that automates the workflow of an equity research analyst. It collects data from 4 sources — Yahoo Finance, Alpha Vantage, NewsAPI, and SEC EDGAR — transforms it through a three-layer Snowflake warehouse, and uses a multi-agent AI pipeline to generate branded 15-20 page PDF equity research reports."

**Key stats to mention:**
- 5 tracked tickers (expandable to 50)
- 4 external data sources
- 12 Snowflake tables across 3 layers
- 8 AI-generated charts per report with VLM refinement
- 19-page branded PDF with investment recommendation

---

### Architecture Overview (3 minutes)

**Reference:** `01-system-architecture.md`

**Talking points:**
1. "The system has four main layers: data ingestion, warehouse transformation, AI analysis, and an interactive frontend."
2. "Data flows from external APIs through our Python data loaders into Snowflake RAW tables, gets transformed by dbt into STAGING views and ANALYTICS tables, and is consumed by both the multi-agent report pipeline and the React frontend."
3. "We use two AI platforms — Snowflake Cortex for data-proximate LLM/VLM inference, and AWS Bedrock for RAG, guardrails, and multi-model consensus."

**Walk through the Mermaid diagram** — point out how each component connects.

---

### Data Pipeline Deep Dive (3 minutes)

**Reference:** `02-data-pipeline-architecture.md` + `03-snowflake-warehouse-architecture.md`

**Talking points:**
1. "All 5 data loaders extend a BaseDataLoader with a template method pattern. This gives us a consistent 5-step workflow — fetch, transform, validate, score quality, and MERGE — for every data source."
2. "The MERGE pattern is critical — it makes every load idempotent. Re-running the pipeline never creates duplicates."
3. "Each record gets a quality score from 0-100 before entering the warehouse. Low-quality records are preserved but flagged."
4. "dbt transforms RAW into STAGING (cleaned views) and ANALYTICS (fact/dimension tables with derived signals like BULLISH/BEARISH)."

**Diagram to show:** Template method pattern flowchart, then the three-layer diagram.

---

### CAVM Pipeline — The Star of the Show (5 minutes)

**Reference:** `04-cavm-pipeline-architecture.md`

**Talking points:**
1. "CAVM stands for Chart-Analysis-Validation-Metrics. It's a 4-agent pipeline that generates professional equity research reports."
2. "The Chart Agent is the core innovation — it uses a **VLM refinement loop**. It generates matplotlib code via Cortex, renders the chart, then sends the actual image to a Vision Language Model for critique. The VLM says 'the labels overlap' or 'the legend is missing,' and the code is regenerated with that feedback."
3. "The Analysis Agent uses **Chain-of-Analysis** — each chart is analyzed serially, with previous analyses fed as context. This creates a narrative where later insights reference earlier findings, like a real analyst would write."
4. "We integrate AWS Bedrock at three points: KB RAG for SEC filing context, Guardrails for content safety (blocks investment advice, redacts PII), and multi-model consensus for the investment thesis."
5. "The Report Agent assembles everything into a branded 19-page PDF with the Midnight Teal color scheme — dark header, teal accents, green for bullish signals, red for bearish."

**Diagrams to show:** VLM refinement loop, Chain-of-Analysis sequence, PDF structure.

---

### Frontend Demo (3 minutes)

**Reference:** `06-frontend-architecture.md`

**Talking points:**
1. "The frontend is a Next.js 16 app with 5 pages, backed by a FastAPI API that queries Snowflake directly."
2. "The design uses an editorial aesthetic with serif headings and warm colors — intentionally different from a typical tech dashboard to match the premium feel of equity research."

**Demo sequence (if live demo):**
1. **Dashboard** — Show KPI cards, signal badges, and price chart for AAPL
2. **Analytics Explorer** — Switch tabs to show stock metrics, fundamentals, sentiment
3. **SEC Filing Analysis** — Show filing inventory, trigger an AI analysis (Summary mode)
4. **Report Generation** — Start a CAVM pipeline, show the 4-stage stepper
5. **Ask FinSage** — Ask "What are the key risk factors for AAPL?"

---

### Orchestration & Infrastructure (2 minutes)

**Reference:** `07-orchestration-architecture.md` + `08-infrastructure-architecture.md`

**Talking points:**
1. "Airflow runs daily at 5 PM EST on weekdays — after market close. It processes 50 tickers in batches of 10 with API-specific rate limiting."
2. "There's a quality gate that blocks dbt from running unless 25+ tickers have fresh data. This prevents stale analytics."
3. "Infrastructure is code-managed: Terraform for S3, Docker Compose for Airflow, dbt for transformations."

---

### Design Decisions (2-3 minutes)

**Reference:** `09-design-decisions-and-tradeoffs.md`

**Pick 3-4 of the strongest decisions to highlight:**

1. **"Why multi-agent instead of monolithic?"**
   > "Each agent fails independently. If chart generation fails for one chart, we use fallback code — the report is still complete. A monolithic script would abort entirely."

2. **"Why VLM refinement?"**
   > "Single-pass LLM-generated charts have a ~60% visual quality rate. The VLM refinement loop catches overlapping labels, missing legends, and wrong colors — improving quality to 85%+."

3. **"Why Chain-of-Analysis?"**
   > "Parallel analysis produces disconnected bullet points. Serial analysis produces a narrative — later insights reference earlier findings, just like a real analyst would write."

4. **"Why both Snowflake Cortex and AWS Bedrock?"**
   > "Cortex keeps data in the warehouse for LLM analysis. Bedrock provides RAG, guardrails for financial compliance, and multi-model consensus — capabilities Cortex doesn't offer."

---

### Closing (1 minute)

**What we learned:**
- Building reliable AI pipelines requires fallback chains at every step
- Data quality scoring before warehouse entry catches issues early
- VLM-in-the-loop for code generation is a powerful pattern
- Chain-of-Analysis creates coherent narratives from independent data points

**What we'd improve:**
- Parameterized SQL queries for security
- Redis-backed task queue instead of in-memory
- Authentication for the frontend
- Snowflake Cortex Search for RAG (replacing Bedrock KB)

---

## Anticipated Hard Questions

### Technical Questions

**Q: "How do you handle concurrent Snowflake sessions?"**
> "Each pipeline stage creates its own Snowpark session. For the parallel analysis sections (company overview, peer comparison, etc.), we spin up separate sessions per thread. The orchestrator manages session lifecycle."

**Q: "What's the Cortex cost?"**
> "Cortex is credit-based, tied to the warehouse. The CAVM pipeline makes ~30 Cortex calls per report (24 for charts + thesis + summaries). On the academic account, this is within the free tier."

**Q: "How do you prevent SQL injection in the API?"**
> "Currently, we sanitize input (uppercase, strip, max_length=10 for tickers). For production, we'd switch to Snowpark parameterized queries. This is a known limitation we'd address."

**Q: "What happens if the LLM hallucinates financial data?"**
> "Three safeguards: (1) Chart data comes from ANALYTICS tables, not LLM generation. (2) Guardrails check contextual grounding — text must be supported by the provided context. (3) The report includes a 'Data Sources' appendix showing exactly which tables and dates were used."

**Q: "How reliable is the VLM refinement?"**
> "The VLM has a 3-tier fallback: claude-sonnet-4-6 → pixtral-large → text-only critique. If all three fail, the chart from the first iteration is used. VLM failures are soft passes — they never block the pipeline."

### Architecture Questions

**Q: "Why not use LangChain?"**
> "LangChain adds abstraction for dynamic agent routing. Our pipeline is linear (Chart → Validate → Analyze → Report) with fixed stages. Direct Python orchestration is simpler, more debuggable, and has zero framework dependencies."

**Q: "How would this scale to 500 tickers?"**
> "The data pipeline already processes tickers in parallel (ThreadPoolExecutor). Scaling to 500 would require: (1) increasing batch size or adding more workers, (2) upgrading API tiers for higher rate limits, (3) larger Snowflake warehouse for dbt. The architecture supports this — no redesign needed."

**Q: "What's the test coverage?"**
> "7 test files with 60+ test cases covering: data loader validation/quality scoring, signal derivation logic, configuration validation, UI helper functions (including XSS testing for badge rendering), and chart generation fallbacks."

### Process Questions

**Q: "How long did this take to build?"**
> "The project evolved iteratively: data pipeline first, then dbt transformations, then the CAVM pipeline, then the frontend. Each component was built and tested independently before integration."

**Q: "What was the hardest part?"**
> "Getting the VLM refinement loop reliable. LLM-generated matplotlib code fails in surprising ways — hallucinated methods, wrong kwargs, date format issues. We added code sanitization, subprocess execution with timeouts, and fallback charts to handle all failure modes."

**Q: "How did you decide on the signal thresholds (BULLISH/BEARISH)?"**
> "Empirically tested against known market conditions. For example, the trend signal uses price vs 30-day SMA and 7-day vs 30-day SMA crossover — a standard technical analysis pattern. Thresholds were validated by comparing signals against actual price movements in our test tickers."

---

## Demo Checklist

If doing a live demo, ensure these are running:
- [ ] FastAPI backend: `cd frontend-react/api && uvicorn main:app --reload --port 8000`
- [ ] Next.js frontend: `cd frontend-react && npm run dev`
- [ ] Snowflake credentials in `.env`
- [ ] At least one generated report in `outputs/` (for showing PDF)

### Demo Script

1. Open the Dashboard → select AAPL → show real-time data
2. Navigate to Analytics → show each tab
3. Navigate to SEC → trigger a Summary analysis
4. Navigate to Report → start a CAVM pipeline (or show a pre-generated PDF)
5. Navigate to Ask → ask a question about AAPL
6. Show Snowflake in browser → show the three schemas (RAW, STAGING, ANALYTICS)
7. Show a generated PDF report → scroll through to show branded layout

---

## File Reference

| Document | Content | When to Reference |
|----------|---------|-------------------|
| `01-system-architecture.md` | High-level overview, tech stack rationale | Opening, architecture overview |
| `02-data-pipeline-architecture.md` | Data loaders, MERGE, quality scoring | Data pipeline deep dive |
| `03-snowflake-warehouse-architecture.md` | Three-layer architecture, dbt, signals | Warehouse section |
| `04-cavm-pipeline-architecture.md` | Multi-agent pipeline, VLM refinement | CAVM deep dive (star section) |
| `05-sec-filing-pipeline.md` | SEC EDGAR, Bedrock KB, Guardrails | AI integration section |
| `06-frontend-architecture.md` | Next.js, FastAPI, API map, design system | Frontend demo |
| `07-orchestration-architecture.md` | Airflow DAG, dbt, Docker Compose | Orchestration section |
| `08-infrastructure-architecture.md` | Snowflake, AWS, Terraform, security | Infrastructure section |
| `09-design-decisions-and-tradeoffs.md` | 15 Q&A entries, known limitations | Q&A preparation |

---

*Previous: [09-design-decisions-and-tradeoffs.md](./09-design-decisions-and-tradeoffs.md)*
