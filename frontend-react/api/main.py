"""FinSage FastAPI Backend — serves Snowflake data to the React frontend."""

from __future__ import annotations

import time
import logging
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path

from routers import dashboard, analytics, sec, report, pipeline, observability, report_chat_router

logger = logging.getLogger("finsage.api")


# ── Request metrics middleware ────────────────────────────────

class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code, and latency for every request."""

    async def dispatch(self, request: Request, call_next):
        t0 = time.time()
        response = await call_next(request)
        latency_ms = round((time.time() - t0) * 1000)
        logger.info(
            "%s %s -> %d (%dms)",
            request.method, request.url.path,
            response.status_code, latency_ms,
        )
        response.headers["X-Response-Time-Ms"] = str(latency_ms)
        return response


app = FastAPI(title="FinSage API", version="1.0.0")

app.add_middleware(RequestMetricsMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(sec.router, prefix="/api/sec", tags=["sec"])
app.include_router(report.router, prefix="/api/report", tags=["report"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(observability.router, prefix="/api/observability", tags=["observability"])
app.include_router(report_chat_router.router, prefix="/api/report_chat", tags=["report_chat"])

# Serve generated PDFs / chart images
outputs_dir = Path(__file__).resolve().parent.parent.parent / "outputs"
if outputs_dir.exists():
    app.mount("/api/files", StaticFiles(directory=str(outputs_dir)), name="files")

from deps import get_tickers


@app.get("/api/tickers")
def list_tickers():
    return get_tickers()


# ── Company name resolution (static map + yfinance fallback) ─
_COMPANY_NAME_CACHE: dict[str, str | None] = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation", "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.", "META": "Meta Platforms Inc.", "TSLA": "Tesla Inc.",
    "NVDA": "NVIDIA Corporation", "JPM": "JPMorgan Chase & Co.", "V": "Visa Inc.",
    "JNJ": "Johnson & Johnson", "WMT": "Walmart Inc.", "PG": "Procter & Gamble Co.",
    "MA": "Mastercard Inc.", "UNH": "UnitedHealth Group Inc.", "HD": "Home Depot Inc.",
    "DIS": "Walt Disney Co.", "BAC": "Bank of America Corp.", "XOM": "Exxon Mobil Corp.",
    "NFLX": "Netflix Inc.", "KO": "Coca-Cola Co.", "PEP": "PepsiCo Inc.",
    "CSCO": "Cisco Systems Inc.", "ADBE": "Adobe Inc.", "CRM": "Salesforce Inc.",
    "ABT": "Abbott Laboratories", "TMO": "Thermo Fisher Scientific Inc.",
    "NKE": "Nike Inc.", "MRK": "Merck & Co. Inc.", "INTC": "Intel Corporation",
    "VZ": "Verizon Communications Inc.", "T": "AT&T Inc.", "CMCSA": "Comcast Corporation",
    "PFE": "Pfizer Inc.", "WFC": "Wells Fargo & Co.", "PM": "Philip Morris International Inc.",
    "MS": "Morgan Stanley", "GS": "Goldman Sachs Group Inc.", "PYPL": "PayPal Holdings Inc.",
    "BLK": "BlackRock Inc.", "CVX": "Chevron Corporation", "AMD": "Advanced Micro Devices Inc.",
    "QCOM": "Qualcomm Inc.", "LOW": "Lowe's Companies Inc.", "INTU": "Intuit Inc.",
    "SBUX": "Starbucks Corporation", "GE": "General Electric Co.", "CAT": "Caterpillar Inc.",
    "BA": "Boeing Co.", "GILD": "Gilead Sciences Inc.", "BKNG": "Booking Holdings Inc.",
}


@app.get("/api/company-name")
def get_company_name(ticker: str = Query(..., description="Stock ticker symbol")):
    """Resolve a human-readable company name for a ticker."""
    clean = ticker.upper().strip()
    if not clean:
        return {"ticker": clean, "company_name": None, "valid": False}

    # Check cache first (includes static map)
    if clean in _COMPANY_NAME_CACHE:
        return {"ticker": clean, "company_name": _COMPANY_NAME_CACHE[clean], "valid": True}

    # yfinance fallback
    try:
        import yfinance as yf
        info = yf.Ticker(clean).info
        name = info.get("shortName") or info.get("longName")
        valid = name is not None or info.get("regularMarketPrice") is not None
        _COMPANY_NAME_CACHE[clean] = name
        return {"ticker": clean, "company_name": name, "valid": valid}
    except Exception:
        _COMPANY_NAME_CACHE[clean] = None
        return {"ticker": clean, "company_name": None, "valid": False}


@app.get("/api/health")
def health():
    try:
        from deps import get_snowpark_session

        gen = get_snowpark_session()
        session = next(gen)
        session.sql("SELECT 1").collect()
        try:
            next(gen)
        except StopIteration:
            pass
        return {"status": "ok", "snowflake": "connected"}
    except Exception as e:
        return {"status": "degraded", "snowflake": str(e)}
