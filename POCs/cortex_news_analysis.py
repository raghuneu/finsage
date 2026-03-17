import os
from dotenv import load_dotenv
from snowflake.snowpark import Session
import pandas as pd

load_dotenv()

# ── 1. Connect via Snowpark ──────────────────────────────────────────────────
def get_session():
    return Session.builder.configs({
        "account":   os.getenv("SNOWFLAKE_ACCOUNT"),
        "user":      os.getenv("SNOWFLAKE_USER"),
        "password":  os.getenv("SNOWFLAKE_PASSWORD"),
        "role":      os.getenv("SNOWFLAKE_ROLE"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database":  os.getenv("SNOWFLAKE_DATABASE"),
        "schema":    "STAGING",   # override RAW → STAGING
    }).create()


# ── 2. SENTIMENT — score every news headline ─────────────────────────────────
def run_sentiment(session, ticker: str = "AAPL") -> pd.DataFrame:
    """
    SNOWFLAKE.CORTEX.SENTIMENT() returns a float between -1 (negative)
    and 1 (positive) for each piece of text. We run it on the headline
    + description combined for richer signal.
    """
    query = f"""
        SELECT
            ticker,
            published_at,
            title,
            SNOWFLAKE.CORTEX.SENTIMENT(
                CONCAT(title, '. ', COALESCE(description, ''))
            ) AS sentiment_score
        FROM FINSAGE_DB.STAGING.STG_NEWS
        WHERE ticker = '{ticker}'
          AND title IS NOT NULL
        ORDER BY published_at DESC
        LIMIT 20
    """
    df = session.sql(query).to_pandas()
    return df


# ── 3. COMPLETE — LLM generates a short analyst commentary ───────────────────
def run_complete(session, ticker: str = "AAPL") -> str:
    """
    SNOWFLAKE.CORTEX.COMPLETE() calls an LLM (we use mistral-large2 here —
    it's available on most Snowflake accounts and is cost-efficient).
    We feed it the top headlines and ask for a 3-sentence market summary.
    """
    # First, pull headlines into Python to build the prompt
    headlines_df = session.sql(f"""
        SELECT title
        FROM FINSAGE_DB.STAGING.STG_NEWS
        WHERE ticker = '{ticker}'
          AND title IS NOT NULL
        ORDER BY published_at DESC
        LIMIT 10
    """).to_pandas()

    headlines = "\n".join(f"- {h}" for h in headlines_df["TITLE"].tolist())

    prompt = f"""You are a financial analyst. Based on the following recent news headlines for {ticker}, 
write a 3-sentence market sentiment summary. Be concise and factual.

Headlines:
{headlines}

Summary:"""

    # Escape single quotes in the prompt for SQL safety
    safe_prompt = prompt.replace("'", "\\'")

    query = f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            'mistral-large2',
            '{safe_prompt}'
        ) AS llm_commentary
    """
    result = session.sql(query).to_pandas()
    return result["LLM_COMMENTARY"].iloc[0]


# ── 4. Main ──────────────────────────────────────────────────────────────────
def main():
    ticker = "AAPL"   # change to TSLA, MSFT, etc.

    print(f"\n{'='*60}")
    print(f"  FinSage — Cortex AI Proof of Concept  |  {ticker}")
    print(f"{'='*60}\n")

    session = get_session()
    print("✅ Connected to Snowflake\n")

    # ── Sentiment ──
    print("📰 Running SENTIMENT on recent news headlines...")
    sentiment_df = run_sentiment(session, ticker)

    # Pretty-print with labels
    def label(score):
        if score > 0.2:   return "🟢 Positive"
        if score < -0.2:  return "🔴 Negative"
        return              "🟡 Neutral"

    print(f"\n{'─'*60}")
    for _, row in sentiment_df.iterrows():
        print(f"{label(row['SENTIMENT_SCORE'])}  ({row['SENTIMENT_SCORE']:+.3f})")
        print(f"  {row['TITLE'][:80]}...")
        print()

    avg = sentiment_df["SENTIMENT_SCORE"].mean()
    print(f"📊 Average sentiment score for {ticker}: {avg:+.3f}  {label(avg)}")

    # ── LLM Commentary ──
    print(f"\n{'─'*60}")
    print("🤖 Running COMPLETE — generating analyst commentary...\n")
    commentary = run_complete(session, ticker)
    print("LLM Commentary:")
    print(f"\n{commentary}\n")

    session.close()
    print("✅ Done.")


if __name__ == "__main__":
    main()