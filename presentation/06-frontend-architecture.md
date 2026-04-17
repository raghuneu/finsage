# Frontend Architecture — Next.js + FastAPI

## What It Does

FinSage has a modern web frontend with a Next.js 16 React app (5 pages) that communicates with a FastAPI Python backend (6 REST routers). The backend queries Snowflake directly via Snowpark sessions and triggers the CAVM pipeline for report generation.

---

## Architecture Overview

```mermaid
graph TB
    subgraph "Browser"
        NJ["Next.js 16<br/>React 19 + TypeScript<br/>Port 3000"]
    end
    
    subgraph "FastAPI Backend (Python)"
        FA["main.py<br/>Port 8000<br/>CORS enabled"]
        
        R1["dashboard.py<br/>/api/dashboard/*"]
        R2["analytics.py<br/>/api/analytics/*"]
        R3["sec.py<br/>/api/sec/*"]
        R4["report.py<br/>/api/report/*"]
        R5["chat.py<br/>/api/chat/*"]
        R6["pipeline.py<br/>/api/pipeline/*"]
        
        FA --> R1
        FA --> R2
        FA --> R3
        FA --> R4
        FA --> R5
        FA --> R6
    end
    
    subgraph "Data Layer"
        SF["Snowflake<br/>ANALYTICS + RAW"]
        DA["Document Agent<br/>(Cortex LLM)"]
        CAVM["CAVM Pipeline<br/>(4 agents)"]
        FS["File System<br/>outputs/ directory"]
    end
    
    NJ -->|"axios<br/>http://localhost:8000"| FA
    
    R1 --> SF
    R2 --> SF
    R3 --> SF
    R3 --> DA
    R4 --> CAVM
    R4 --> FS
    R5 --> DA
    R6 --> SF
    
    FA -->|"/api/files/*<br/>Static file serving"| FS
```

---

## Frontend Page Map

```mermaid
graph TD
    subgraph "App Shell (AppShell.tsx)"
        NAV["Sidebar Navigation<br/>220px drawer<br/>Ticker selector at top"]
        
        subgraph "Pages"
            P1["/ — Dashboard<br/>KPIs + Price Chart + Headlines"]
            P2["/analytics — Analytics Explorer<br/>4-tab layout: Stock, Fundamentals,<br/>Sentiment, SEC Financials"]
            P3["/sec — SEC Filing Analysis<br/>Filing inventory + AI analysis<br/>(Summary, Risk, MD&A, Compare)"]
            P4["/report — Report Generation<br/>Quick Report (Cortex) +<br/>Full CAVM Pipeline (4-stage stepper)"]
            P5["/ask — Ask FinSage<br/>Chat interface with<br/>Snowflake Cortex"]
        end
    end
    
    NAV --> P1
    NAV --> P2
    NAV --> P3
    NAV --> P4
    NAV --> P5
```

---

## Component Hierarchy

```mermaid
graph TD
    APP["app/layout.tsx<br/>ThemeRegistry + TickerProvider"]
    APP --> SHELL["AppShell.tsx<br/>Sidebar + Header + Content"]
    
    SHELL --> DASH["Dashboard Page"]
    SHELL --> ANALYTICS["Analytics Page"]
    SHELL --> SEC["SEC Page"]
    SHELL --> REPORT["Report Page"]
    SHELL --> ASK["Ask Page"]
    
    DASH --> MC["MetricCard × 5<br/>(Market Cap, Price,<br/>Revenue, Sentiment, P/E)"]
    DASH --> SB["SignalBadge × 4<br/>(Trend, Fundamentals,<br/>Sentiment, Health)"]
    DASH --> PC["PriceChart<br/>(lightweight-charts)"]
    
    ANALYTICS --> PC2["PriceChart<br/>(Stock Metrics tab)"]
    ANALYTICS --> RC["Recharts<br/>(Fundamentals, Sentiment,<br/>SEC Financials tabs)"]
    
    ASK --> CM["ChatMessage<br/>(user + assistant bubbles)"]
    
    REPORT --> STEPPER["MUI Stepper<br/>(CAVM 4-stage progress)"]
    
    subgraph "Shared Components"
        MC
        SB
        PC
        CM
        SH["SectionHeader"]
        LS["LoadingSkeleton"]
    end
```

---

## Design System — "Fancy Flirt" Theme

### Color Palette

| Color | Name | Hex | Usage |
|-------|------|-----|-------|
| ![#0382B7](https://placehold.co/15x15/0382B7/0382B7.png) | Star Command Blue | `#0382B7` | Primary / interactive elements / price line |
| ![#9DCBB8](https://placehold.co/15x15/9DCBB8/9DCBB8.png) | Rare Jade | `#9DCBB8` | Success / bullish signals |
| ![#C96BAE](https://placehold.co/15x15/C96BAE/C96BAE.png) | Super Pink | `#C96BAE` | Accent / active navigation / section borders |
| ![#E58B6D](https://placehold.co/15x15/E58B6D/E58B6D.png) | Trendy Coral | `#E58B6D` | Warning / bearish signals |
| ![#F8CB86](https://placehold.co/15x15/F8CB86/F8CB86.png) | Sky Yellow | `#F8CB86` | Highlights / chart accents |
| ![#FAFAF7](https://placehold.co/15x15/FAFAF7/FAFAF7.png) | Background | `#FAFAF7` | Warm off-white page background |

### Typography

| Style | Font | Usage |
|-------|------|-------|
| Headings | **DM Serif Display** (serif) | Page titles, metric values, section headers |
| Body | **DM Sans** (sans-serif) | Body text, labels, navigation |

**Why this design:** An editorial, warm aesthetic that differentiates from typical blue-on-white tech dashboards. The serif headings give a financial report feel, while the warm colors create a premium, approachable interface.

### Component Styling

| Component | Style Details |
|-----------|--------------|
| **Cards** | White background, `#E8E4DB` border, subtle shadow, 10px radius |
| **Buttons** | Pink → Blue gradient for primary, 8px radius |
| **Sidebar** | `#F2F0EB` background, pink active indicator |
| **SignalBadge** | Color-coded chips: jade (bullish), yellow (neutral), gray (no data), coral (bearish) |
| **MetricCard** | Gradient top border (pink → blue), large serif value, delta with trend arrow |

---

## API Endpoint Map

### Dashboard Router (`/api/dashboard/`)

| Endpoint | Method | Response | Data Source |
|----------|--------|----------|-------------|
| `/kpis` | GET | Market cap, price, revenue, sentiment, P/E, 4 signals | 5 ANALYTICS tables |
| `/price-history` | GET | OHLCV + SMA data (N days) | FCT_STOCK_METRICS |
| `/headlines` | GET | Recent news titles with dates | RAW_NEWS |

### Analytics Router (`/api/analytics/`)

| Endpoint | Method | Response | Data Source |
|----------|--------|----------|-------------|
| `/stock-metrics` | GET | OHLCV, SMAs, volatility, trend signal | FCT_STOCK_METRICS |
| `/fundamentals` | GET | Revenue, EPS, growth rates, signal | FCT_FUNDAMENTALS_GROWTH |
| `/sentiment` | GET | Scores, article counts, 7D avg, trend | FCT_NEWS_SENTIMENT_AGG |
| `/sec-financials` | GET | Margins, ROE, D/E, health signal | FCT_SEC_FINANCIAL_SUMMARY |

### SEC Router (`/api/sec/`)

| Endpoint | Method | Response | Data Source |
|----------|--------|----------|-------------|
| `/filings` | GET | Filing inventory list | RAW_SEC_FILING_DOCUMENTS → RAW_SEC_FILINGS (fallback) |
| `/analyze` | POST | AI analysis (4 modes) | Document Agent + Cortex |

### Report Router (`/api/report/`)

| Endpoint | Method | Response | Data Source |
|----------|--------|----------|-------------|
| `/quick` | POST | Markdown report (synchronous) | Document Agent |
| `/cavm` | POST | Task ID (async pipeline start) | CAVM Pipeline (background thread) |
| `/cavm/status/{id}` | GET | Pipeline progress + PDF URL | In-memory task store |
| `/download/{file}` | GET | PDF file download | outputs/ directory |

### Chat Router (`/api/chat/`)

| Endpoint | Method | Response | Data Source |
|----------|--------|----------|-------------|
| `/ask` | POST | AI answer with citations | Document Agent + Cortex |

### Pipeline Router (`/api/pipeline/`)

| Endpoint | Method | Response | Data Source |
|----------|--------|----------|-------------|
| `/readiness` | POST | Data availability check | RAW/ANALYTICS tables |
| `/load` | POST | Task ID (async data load) | Data loaders (background) |
| `/load/status/{id}` | GET | Load job progress | In-memory task store |

---

## Data Flow: Dashboard Page Example

```mermaid
sequenceDiagram
    participant Browser as Next.js (Browser)
    participant API as lib/api.ts
    participant FastAPI as FastAPI Backend
    participant SF as Snowflake

    Browser->>Browser: useTicker() → "AAPL"
    Browser->>Browser: useEffect triggers on ticker change
    
    par Parallel API calls
        Browser->>API: fetchKPIs("AAPL")
        API->>FastAPI: GET /api/dashboard/kpis?ticker=AAPL
        FastAPI->>SF: Query 5 ANALYTICS tables
        SF-->>FastAPI: Aggregated metrics
        FastAPI-->>API: JSON response
        API-->>Browser: KPI data
        
        Browser->>API: fetchPriceHistory("AAPL", 90)
        API->>FastAPI: GET /api/dashboard/price-history?ticker=AAPL&days=90
        FastAPI->>SF: Query FCT_STOCK_METRICS
        SF-->>FastAPI: 90 rows of OHLCV + SMA
        FastAPI-->>API: JSON array
        API-->>Browser: Price history
        
        Browser->>API: fetchHeadlines("AAPL")
        API->>FastAPI: GET /api/dashboard/headlines?ticker=AAPL
        FastAPI->>SF: Query RAW_NEWS
        SF-->>FastAPI: Recent articles
        FastAPI-->>API: JSON array
        API-->>Browser: Headlines
    end
    
    Browser->>Browser: Render MetricCards + SignalBadges + PriceChart + Headlines
```

---

## CAVM Pipeline — Async Flow

```mermaid
sequenceDiagram
    participant Browser as Next.js
    participant API as FastAPI
    participant Thread as Background Thread
    participant CAVM as CAVM Pipeline

    Browser->>API: POST /api/report/cavm {ticker: "AAPL"}
    API->>API: check_data_readiness("AAPL")
    
    alt Data missing + auto_load=true
        API->>API: ensure_data_for_ticker("AAPL")
    end
    
    API->>Thread: Start background thread
    API-->>Browser: {task_id: "abc123", status: "running"}
    
    Thread->>CAVM: Run 4-stage pipeline
    
    loop Poll every 5 seconds
        Browser->>API: GET /api/report/cavm/status/abc123
        API-->>Browser: {stage: "chart_generation", progress: 35%}
    end
    
    CAVM-->>Thread: Complete — PDF at outputs/AAPL_.../report.pdf
    Thread->>Thread: Update _tasks["abc123"]
    
    Browser->>API: GET /api/report/cavm/status/abc123
    API-->>Browser: {status: "completed", pdf_url: "/api/files/AAPL_.../report.pdf"}
    
    Browser->>API: GET /api/files/AAPL_.../report.pdf
    API-->>Browser: PDF file download
```

---

## Ticker Context — App-Wide State

```mermaid
flowchart TD
    A["TickerProvider<br/>(app/layout.tsx)"] --> B["React Context:<br/>ticker, setTicker, tickers[]"]
    
    B --> C["AppShell.tsx<br/>Ticker autocomplete selector"]
    B --> D["Dashboard page<br/>useTicker() → API calls"]
    B --> E["Analytics page<br/>useTicker() → chart data"]
    B --> F["SEC page<br/>useTicker() → filing list"]
    B --> G["Report page<br/>useTicker() → pipeline target"]
    B --> H["Ask page<br/>useTicker() → chat context"]
    
    C -->|"User selects ticker"| I["setTicker('MSFT')"]
    I -->|"All pages re-render"| D & E & F & G & H
```

**How it works:**
1. On mount, fetches available tickers from `/api/tickers`
2. Default: AAPL, with fallback list `['AAPL', 'GOOGL', 'JPM', 'MSFT', 'TSLA']`
3. Input sanitization: strips non-alphanumeric, uppercases
4. Dynamically adds new tickers to the suggestion list when typed

---

## Q&A for This Section

**Q: Why a separate FastAPI backend instead of Next.js API routes?**
A: The backend needs Snowflake Snowpark (Python), data loaders (Python), and the CAVM pipeline (Python). Keeping the Python backend separate avoids complex Python-in-Node bridges and lets the data team work in their native language.

**Q: Why not use WebSockets for the CAVM progress updates?**
A: Polling every 5 seconds is simple and sufficient for a 5-15 minute pipeline. WebSockets would add connection management complexity for minimal UX improvement.

**Q: How do you handle the 5-15 minute CAVM pipeline without the request timing out?**
A: The CAVM pipeline runs in a background thread. The API immediately returns a `task_id`, and the frontend polls for status. This is the async task pattern — no long HTTP connections.

**Q: Why MUI instead of Tailwind or Chakra UI?**
A: MUI provides a comprehensive component library (DataGrid, Stepper, Autocomplete, Drawer) that would take significant effort to build from scratch with Tailwind. The theme system allows full customization of the editorial design.

**Q: Why lightweight-charts for the price chart?**
A: lightweight-charts (by TradingView) is purpose-built for financial OHLCV charts with high performance. Recharts and Chart.js lack native candlestick/financial chart support.

---

*Previous: [05-sec-filing-pipeline.md](./05-sec-filing-pipeline.md) | Next: [07-orchestration-architecture.md](./07-orchestration-architecture.md)*
