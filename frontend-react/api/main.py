"""FinSage FastAPI Backend — serves Snowflake data to the React frontend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from routers import dashboard, analytics, sec, report, chat

app = FastAPI(title="FinSage API", version="1.0.0")

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
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

# Serve generated PDFs / chart images
outputs_dir = Path(__file__).resolve().parent.parent.parent / "outputs"
if outputs_dir.exists():
    app.mount("/api/files", StaticFiles(directory=str(outputs_dir)), name="files")

from deps import get_tickers


@app.get("/api/tickers")
def list_tickers():
    return get_tickers()


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
