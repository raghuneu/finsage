# CAVM Multi-Agent Pipeline Architecture

## What It Does

The CAVM (Chart-Analysis-Validation-Metrics) pipeline is a 4-agent system that generates branded equity research PDF reports. Given a ticker symbol, it produces 8 professional charts, validates their quality, generates AI-driven analysis with cross-referencing, and assembles a 15-20 page branded PDF.

**Entry point:** `python agents/orchestrator.py --ticker AAPL`

---

## Pipeline Overview

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator
    participant ChartAgent
    participant ValidationAgent
    participant AnalysisAgent
    participant ReportAgent
    participant Cortex as Snowflake Cortex
    participant Bedrock as AWS Bedrock

    User->>Orchestrator: --ticker AAPL
    
    Note over Orchestrator: Stage 1: Chart Generation
    Orchestrator->>ChartAgent: generate_charts(session, ticker)
    
    loop 8 charts (parallel, 4 workers)
        ChartAgent->>Cortex: COMPLETE(claude-opus-4-6, prompt)
        Note over ChartAgent: Generate matplotlib code
        ChartAgent->>ChartAgent: execute_chart_code() [subprocess]
        ChartAgent->>Cortex: COMPLETE(claude-sonnet-4-6, image, critique)
        Note over ChartAgent: VLM critiques the image
        ChartAgent->>Cortex: COMPLETE(claude-opus-4-6, refined prompt)
        Note over ChartAgent: Iteration 2 with feedback
    end
    ChartAgent-->>Orchestrator: 8 chart PNGs + manifest
    
    Note over Orchestrator: Stage 2: Validation
    Orchestrator->>ValidationAgent: validate_all_charts(charts)
    
    loop Each chart (parallel, 4 workers)
        ValidationAgent->>ValidationAgent: Rule-based checks
        ValidationAgent->>Cortex: VLM quality check
    end
    
    alt Failed charts exist
        ValidationAgent->>ChartAgent: Re-render with fallback code
        ValidationAgent->>ValidationAgent: Re-validate
    end
    ValidationAgent-->>Orchestrator: Validated charts
    
    Note over Orchestrator: Stage 3: Analysis
    Orchestrator->>AnalysisAgent: run_analysis(charts, session)
    
    loop 8 charts (serial — Chain-of-Analysis)
        AnalysisAgent->>Cortex: COMPLETE(mistral-large, chart + prior analyses)
        AnalysisAgent->>Bedrock: KB RAG — SEC filing context
        AnalysisAgent->>Bedrock: Guardrails — validate output
    end
    
    par Parallel section analyses
        AnalysisAgent->>AnalysisAgent: Company Overview
        AnalysisAgent->>AnalysisAgent: Peer Comparison
        AnalysisAgent->>AnalysisAgent: Financial Deep Dive
        AnalysisAgent->>AnalysisAgent: Valuation Analysis
    end
    
    AnalysisAgent->>Bedrock: Multi-model consensus (thesis)
    AnalysisAgent-->>Orchestrator: All analyses + thesis
    
    Note over Orchestrator: Stage 4: PDF Report
    Orchestrator->>ReportAgent: generate_report(charts, analyses)
    ReportAgent->>ReportAgent: Build 19-page branded PDF
    ReportAgent-->>Orchestrator: PDF file path
    
    Orchestrator-->>User: outputs/AAPL_YYYYMMDD_HHMMSS/
```

---

## Stage 1: Chart Agent — VLM Refinement Loop

### What: The Core Innovation

Instead of generating charts in a single pass, the Chart Agent uses a **multi-iteration refinement loop** where a Vision Language Model (VLM) critiques each chart image, and the feedback is fed back to improve the next iteration.

### How It Works

```mermaid
flowchart TD
    A["Fetch data from ANALYTICS tables<br/>(4 tables, Snowpark SQL)"] --> B["Precompute columns<br/>(chart_data_prep.py)"]
    B --> C["Validate data sufficiency<br/>(chart_validation.py)"]
    C --> D["For each of 8 charts<br/>(ThreadPoolExecutor, 4 workers)"]
    
    D --> E["Iteration 1:<br/>Build prompt from chart_specs.py constraints<br/>+ iter1_prompt template"]
    E --> F["Cortex COMPLETE (claude-opus-4-6)<br/>Generate matplotlib code"]
    F --> G["Execute in subprocess<br/>(30s timeout, sandboxed)"]
    G --> H{Render success?}
    
    H -->|Yes| I["Upload PNG to @CHART_IMAGES_STAGE"]
    H -->|No| M["Try fallback code"]
    
    I --> J["VLM Critique (claude-sonnet-4-6)<br/>via TO_FILE() multimodal call<br/>Score: 1-10, issues, improvements"]
    
    J --> K["Iteration 2:<br/>Feed critique into iter2_prompt<br/>+ previous code + improvements"]
    K --> L["Cortex COMPLETE → execute → save"]
    
    L --> N["Save final chart PNG"]
    M --> N
    
    N --> O["Save chart_manifest.json"]
```

### Why VLM Refinement

| Problem | Solution |
|---------|----------|
| LLMs generate matplotlib code with visual bugs (overlapping labels, wrong colors, cut-off titles) | VLM sees the actual rendered image and provides specific feedback |
| Single-pass generation has ~60% visual quality rate | 2-iteration refinement improves to ~85%+ quality |
| VLM models can be unreliable | 3-tier VLM fallback: claude-sonnet-4-6 → pixtral-large → text-only critique |

### The 8 Charts

| Chart ID | Type | Data Source | Key Visuals |
|----------|------|-------------|-------------|
| `price_sma` | Line + fill | FCT_STOCK_METRICS | Close price + 3 SMA overlays (7/30/90d) |
| `volatility` | Dual-axis bar+line | FCT_STOCK_METRICS | Volume bars + volatility line |
| `revenue_growth` | Grouped bar | FCT_FUNDAMENTALS_GROWTH | YoY revenue vs net income growth |
| `eps_trend` | Dual-axis line+bar | FCT_FUNDAMENTALS_GROWTH | EPS trend line + growth bars |
| `financial_health` | Dual-axis bar+line | FCT_SEC_FINANCIAL_SUMMARY | Margin bars + D/E ratio line |
| `margin_trend` | Line + fill | FCT_SEC_FINANCIAL_SUMMARY | Net + operating margin trends |
| `balance_sheet` | Stacked bar + line | FCT_SEC_FINANCIAL_SUMMARY | Liabilities, equity stacked + assets line |
| `sentiment` | Line + fill zones | FCT_NEWS_SENTIMENT_AGG | 7-day avg sentiment with bullish/bearish zones |

### Chart Spec Constraints (chart_specs.py)

**Why:** The LLM's job is constrained to *arranging pre-defined data series into matplotlib code* — NOT computing or transforming data. This prevents hallucinated calculations.

Each chart spec defines:
- `chart_type` — matplotlib chart style
- `required_series` — exact column names to plot
- `required_visuals` — mandatory visual elements (legend, title, axis labels)
- `constraints` — hard rules (e.g., "do NOT reorder dates", "use exactly these colors")
- `precomputed_columns` — columns already calculated by `chart_data_prep.py`
- `figsize` — exact figure dimensions

### Code Execution Safety

LLM-generated matplotlib code runs in a **subprocess** with:
- 30-second execution timeout
- Known bad kwarg fixes (`fillalpha=` → `alpha=`, `lineStyle=` → `linestyle=`)
- Hallucinated matplotlib method removal
- Auto date-column conversion (epoch → datetime)
- Try/except wrapper for error capture

---

## Stage 2: Validation Agent — Two-Tier Quality Assurance

```mermaid
flowchart TD
    A[Chart PNG from Stage 1] --> B{Tier 1: Rule-based checks}
    
    B --> C[File exists?]
    B --> D["File size > 10KB?"]
    B --> E["Dimensions ≥ 800x400px?"]
    B --> F[Data summary populated?]
    B --> G["Data plausible?<br/>(margins < 100%, D/E < 50)"]
    
    C & D & E & F & G --> H{All rules pass?}
    
    H -->|No| I["FAIL — skip VLM<br/>Flag for re-render"]
    H -->|Yes| J{Tier 2: VLM quality check}
    
    J --> K["vision_critique() via Cortex<br/>Evaluate: title, axes, colors,<br/>data density, legend<br/>Score 1-10"]
    
    K --> L{Score ≥ 6?}
    L -->|Yes| M[PASS]
    L -->|No| N["SOFT PASS<br/>(VLM failures don't block)"]
    
    I --> O["Re-render with fallback_code<br/>(hardcoded professional chart)"]
    O --> P[Re-validate]
```

**Why VLM failures are soft passes:** VLM models are non-deterministic and occasionally return low scores for perfectly valid charts. Blocking report generation on VLM flakiness would make the pipeline unreliable.

---

## Stage 3: Analysis Agent — Chain-of-Analysis

### What: Progressive Narrative Building

Charts are analyzed **serially in a fixed order** (price → volatility → revenue → EPS → financial_health → margin_trend → balance_sheet → sentiment). Each analysis receives all prior analyses as context, creating a **progressive narrative** where later insights reference and build upon earlier findings.

### How It Works

```mermaid
flowchart TD
    A["Chart 1: price_sma"] --> B["Cortex COMPLETE<br/>+ SEC KB context<br/>+ Guardrails check"]
    B --> C["Analysis 1:<br/>'Price shows upward trend...'"]
    
    C --> D["Chart 2: volatility<br/>+ prior: Analysis 1"]
    D --> E["Analysis 2:<br/>'Consistent with the upward<br/>price trend, volatility...'"]
    
    E --> F["Chart 3: revenue_growth<br/>+ prior: Analysis 1+2"]
    F --> G["Analysis 3:<br/>'Revenue growth supports<br/>the bullish price action...'"]
    
    G --> H["... continue for all 8 charts"]
    
    H --> I["Investment Thesis Synthesis<br/>(Multi-model consensus)"]
```

### Why Chain-of-Analysis (not parallel)

| Parallel Analysis | Chain-of-Analysis |
|-------------------|-------------------|
| Each chart analyzed in isolation | Each analysis references prior findings |
| Disconnected bullet points | Coherent narrative with "consistent with..." and "in contrast to..." |
| No cross-chart insights | Divergences flagged as risks or opportunities |
| Faster but shallow | Slower but reads like a real analyst's report |

### Three Bedrock Integrations

```mermaid
flowchart LR
    subgraph "Per-Chart Analysis"
        A[LLM Analysis<br/>Cortex COMPLETE] --> B[Bedrock KB RAG<br/>SEC filing context]
        B --> C[Guardrails<br/>Content safety]
    end
    
    subgraph "Thesis Generation"
        D[Multi-Model<br/>Llama3 + Titan + Mistral] --> E[Consensus<br/>Synthesis]
    end
    
    A --> D
```

| Integration | Purpose | Fallback |
|------------|---------|----------|
| **Bedrock KB RAG** | Enrich each chart analysis with relevant SEC filing excerpts | Skip — analysis proceeds without SEC context |
| **Guardrails** | Block investment advice, redact PII, detect hallucinations | Replace with fallback text |
| **Multi-Model** | Generate consensus investment thesis from multiple LLMs | Single Cortex call |

### Parallel Section Analyses (Stage 3b/3c)

After the serial chart analyses, 4 additional sections run in parallel using separate Snowflake sessions:

| Section | Content | Data Source |
|---------|---------|-------------|
| Company Overview | AI description, business segments, competitive landscape | DIM_COMPANY + KB |
| Peer Comparison | Metrics comparison vs industry peers | Resolved via yfinance/sector defaults |
| Financial Deep Dive | Multi-quarter trend analysis | FCT_SEC_FINANCIAL_SUMMARY |
| Valuation Analysis | Relative valuation multiples vs peers | Multiple analytics tables |

---

## Stage 4: Report Agent — Branded PDF Assembly

### PDF Structure (19 pages)

```mermaid
graph TD
    subgraph "Pages 1-2"
        P1["Cover Page<br/>Ticker, BUY/HOLD/SELL badge,<br/>3 metric boxes"]
        P2["Table of Contents<br/>+ Methodology callout"]
    end
    
    subgraph "Pages 3-5"
        P3["Executive Summary<br/>9-metric grid, thesis,<br/>signal table"]
        P5["Company Overview<br/>AI description, key facts,<br/>business segments"]
    end
    
    subgraph "Pages 6-13 (1 per chart)"
        P6["Chart Section<br/>Header bar + chart image<br/>+ metrics + AI analysis"]
    end
    
    subgraph "Pages 14-19"
        P14["Financial Metrics<br/>3 detailed tables"]
        P15["Peer Comparison<br/>Metrics table + narrative"]
        P16["Risk Factors<br/>SEC-derived + data-driven"]
        P18["Investment Recommendation<br/>Signal badge + thesis"]
        P19["Appendix<br/>Data sources, chart metadata,<br/>CAVM pipeline, disclaimer"]
    end
    
    P1 --> P2 --> P3 --> P5 --> P6 --> P14 --> P15 --> P16 --> P18 --> P19
```

### Midnight Teal Color Scheme

| Color | Hex | Usage |
|-------|-----|-------|
| Dark | `#0f2027` | Header/footer backgrounds |
| Teal | `#00b4d8` | Accent lines, section headers |
| Bullish | `#06d6a0` | Positive signals, BUY recommendation |
| Bearish | `#ef476f` | Negative signals, SELL recommendation |
| Neutral | `#94a3b8` | Neutral/HOLD signals |

### Signal-to-Recommendation Mapping

```mermaid
flowchart TD
    A["Aggregate all 4 signals"] --> B{Count comparison}
    B -->|"Bullish > Bearish + 1"| C["Overall: BULLISH"]
    B -->|"Bearish > Bullish + 1"| D["Overall: BEARISH"]
    B -->|Otherwise| E["Overall: NEUTRAL"]
    
    C --> F["BUY<br/>Price target: current × 1.12"]
    D --> G["SELL<br/>Price target: current × 0.88"]
    E --> H["HOLD<br/>Price target: current × 1.03"]
```

---

## Orchestrator Coordination

```mermaid
flowchart TD
    A["orchestrator.py<br/>--ticker AAPL --debug"] --> B["Create output directory<br/>outputs/AAPL_YYYYMMDD_HHMMSS/"]
    
    B --> C["Stage 1: generate_charts()"]
    C --> D{Success?}
    D -->|No| E["Abort — no charts"]
    D -->|Yes| F["Stage 2: validate_all_charts()"]
    
    F --> G["Retry failed charts (max 3 attempts)"]
    G --> H["Stage 3a: analyze_all_charts() — serial"]
    
    H --> I["Stage 3b+3c: Parallel analyses<br/>(separate Snowflake sessions)"]
    I --> J["Stage 3d: synthesize_analyses()<br/>(multi-model consensus thesis)"]
    
    J --> K["Stage 4: generate_report()"]
    K --> L["Save pipeline_result.json"]
    L --> M["Done — PDF + charts in outputs/"]
```

**Key design decisions:**
- **Separate Snowflake sessions for parallel Stage 3**: Snowpark sessions aren't thread-safe, so parallel sections get their own sessions
- **`--skip-charts` flag**: Reuse charts from a previous run for faster iteration on analysis/report changes
- **`--debug` flag**: Extra logging, intermediate file preservation

---

## Q&A for This Section

**Q: Why 4 separate agents instead of one monolithic script?**
A: Each agent has a distinct responsibility and failure mode. Chart generation can fail independently of analysis. Validation can trigger re-renders. This separation enables retry logic at each stage and makes debugging easier.

**Q: Why use Snowflake Cortex instead of calling OpenAI/Anthropic directly?**
A: Cortex runs inside Snowflake — no API keys, no data leaves the warehouse, lower latency for data-proximate inference. The SQL interface (`SELECT CORTEX.COMPLETE(...)`) integrates naturally with the Snowpark-based pipeline.

**Q: Why not use LangChain or CrewAI for the multi-agent pipeline?**
A: The CAVM pipeline has a fixed, linear flow (Chart → Validate → Analyze → Report). Agent frameworks add abstraction overhead for what is fundamentally a sequential pipeline with targeted parallelism. Direct Python orchestration is simpler and more debuggable.

**Q: How long does the full pipeline take?**
A: Typically 5-15 minutes per ticker. Chart generation (with VLM refinement) is the bottleneck. The `--skip-charts` flag reduces subsequent runs to 2-5 minutes.

**Q: What happens if a chart completely fails?**
A: The hardcoded `fallback_code` in `CHART_DEFINITIONS` produces a professional-looking chart without any LLM involvement. This ensures the report always has complete visualizations.

---

*Previous: [03-snowflake-warehouse-architecture.md](./03-snowflake-warehouse-architecture.md) | Next: [05-sec-filing-pipeline.md](./05-sec-filing-pipeline.md)*
