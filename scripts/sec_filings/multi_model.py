"""
FinSage Multi-Model Comparison.

Runs the same financial analysis through multiple Bedrock models
and compares their outputs. Generates a consensus score showing
where models agree and disagree.

This delivers on FinSage's original promise of multi-LLM analysis
(Gemini/Llama/Claude) that was in the README but never implemented.

Available models on Bedrock:
    - meta.llama3-8b-instruct-v1:0 (fast, good for quick analysis)
    - meta.llama3-70b-instruct-v1:0 (stronger reasoning)
    - amazon.titan-text-express-v1 (AWS native)
    - mistral.mistral-7b-instruct-v0:2 (efficient)
    - mistral.mixtral-8x7b-instruct-v0:1 (strong multi-task)

Usage:
    from sec_filings.multi_model import MultiModelAnalyzer

    analyzer = MultiModelAnalyzer()
    result = analyzer.compare("What are Apple's main risks?", context="...")
    print(result["consensus"])
    for model, output in result["responses"].items():
        print(f"{model}: {output[:200]}")

CLI:
    python -m sec_filings.multi_model --question "What are Apple's main risks?" --ticker AAPL
    python -m sec_filings.multi_model --question "Rate Apple's financial health" --ticker AAPL --mode consensus
"""

import os
import json
import logging
import time
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# Default models to compare
DEFAULT_MODELS = [
    "meta.llama3-8b-instruct-v1:0",
    "amazon.titan-text-express-v1",
    "mistral.mistral-7b-instruct-v0:2",
]


class MultiModelAnalyzer:
    """Run the same analysis through multiple Bedrock models."""

    def __init__(self, models=None, region=None, guardrail_id=None,
                 guardrail_version=None):
        self.models = models or DEFAULT_MODELS
        self.region = region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.guardrail_id = guardrail_id or os.getenv("BEDROCK_GUARDRAIL_ID")
        self.guardrail_version = guardrail_version or os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")

        self.client = boto3.client("bedrock-runtime", region_name=self.region)

        logger.info("MultiModelAnalyzer initialized with %d models", len(self.models))

    def _call_model(self, model_id: str, prompt: str, max_tokens: int = 1000) -> dict:
        """Call a single Bedrock model and return the response."""
        start_time = time.time()

        try:
            # Build request based on model provider
            if model_id.startswith("meta.llama"):
                body = {
                    "prompt": f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
                    "max_gen_len": max_tokens,
                    "temperature": 0.3,
                }
                response = self.client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                )
                result = json.loads(response["body"].read())
                output = result.get("generation", "")

            elif model_id.startswith("amazon.titan"):
                body = {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": max_tokens,
                        "temperature": 0.3,
                    }
                }
                response = self.client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                )
                result = json.loads(response["body"].read())
                output = result.get("results", [{}])[0].get("outputText", "")

            elif model_id.startswith("mistral"):
                body = {
                    "prompt": f"<s>[INST] {prompt} [/INST]",
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                }
                response = self.client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                )
                result = json.loads(response["body"].read())
                output = result.get("outputs", [{}])[0].get("text", "")

            elif model_id.startswith("anthropic.claude"):
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                }
                response = self.client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                )
                result = json.loads(response["body"].read())
                output = result.get("content", [{}])[0].get("text", "")

            else:
                return {
                    "model": model_id,
                    "output": "",
                    "error": f"Unsupported model: {model_id}",
                    "latency_ms": 0,
                    "success": False,
                }

            latency = (time.time() - start_time) * 1000

            logger.info("Model %s responded in %.0fms (%d chars)",
                        model_id, latency, len(output))

            return {
                "model": model_id,
                "output": output.strip(),
                "error": None,
                "latency_ms": round(latency),
                "success": True,
            }

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error("Model %s failed: %s", model_id, e)
            return {
                "model": model_id,
                "output": "",
                "error": str(e),
                "latency_ms": round(latency),
                "success": False,
            }

    def compare(self, question: str, context: str = None,
                models: list = None) -> dict:
        """
        Run the same question through multiple models and compare.

        Args:
            question: The analysis question
            context: Optional source data (SEC filing text, analytics)
            models: Override default model list

        Returns:
            dict with 'responses', 'summary', 'fastest_model', 'all_succeeded'
        """
        models_to_use = models or self.models

        # Build the full prompt
        if context:
            prompt = f"""You are a senior financial analyst. Answer the following question 
based on the provided data. Be specific with numbers and keep your answer under 300 words.

SOURCE DATA:
{context[:15000]}

QUESTION: {question}

ANSWER:"""
        else:
            prompt = f"""You are a senior financial analyst. Answer the following question.
Be specific and keep your answer under 300 words.

QUESTION: {question}

ANSWER:"""

        # Run all models in parallel
        responses = {}
        with ThreadPoolExecutor(max_workers=len(models_to_use)) as executor:
            futures = {
                executor.submit(self._call_model, model, prompt): model
                for model in models_to_use
            }

            for future in as_completed(futures):
                result = future.result()
                model_name = result["model"].split(".")[-1].split("-v")[0]
                responses[model_name] = result

        # Calculate stats
        successful = [r for r in responses.values() if r["success"]]
        failed = [r for r in responses.values() if not r["success"]]

        fastest = min(successful, key=lambda x: x["latency_ms"]) if successful else None
        slowest = max(successful, key=lambda x: x["latency_ms"]) if successful else None

        summary = {
            "total_models": len(models_to_use),
            "succeeded": len(successful),
            "failed": len(failed),
            "fastest_model": fastest["model"] if fastest else None,
            "fastest_ms": fastest["latency_ms"] if fastest else None,
            "slowest_model": slowest["model"] if slowest else None,
            "slowest_ms": slowest["latency_ms"] if slowest else None,
        }

        return {
            "question": question,
            "responses": responses,
            "summary": summary,
            "all_succeeded": len(failed) == 0,
        }

    def consensus(self, question: str, context: str = None) -> dict:
        """
        Run comparison and then ask a model to synthesize a consensus.

        Returns the individual responses PLUS a consensus analysis
        highlighting where models agree and disagree.
        """
        # Get individual responses
        comparison = self.compare(question, context)

        successful_responses = {
            name: r for name, r in comparison["responses"].items()
            if r["success"]
        }

        if len(successful_responses) < 2:
            comparison["consensus"] = "Need at least 2 successful model responses for consensus."
            return comparison

        # Build consensus prompt
        model_outputs = ""
        for name, r in successful_responses.items():
            model_outputs += f"\n--- {name} ---\n{r['output'][:800]}\n"

        consensus_prompt = f"""You are a meta-analyst reviewing financial analyses from multiple AI models.
Each model was asked the same question about a company.

QUESTION: {question}

MODEL RESPONSES:
{model_outputs}

Provide a consensus analysis:

1. AGREEMENT — What do ALL models agree on? (List specific claims)
2. DISAGREEMENT — Where do models differ? Which model is likely more accurate and why?
3. CONFIDENCE SCORE — Rate overall consensus 1-10 (10 = perfect agreement)
4. SYNTHESIZED ANSWER — Combine the best insights from all models into one definitive answer

Keep under 400 words."""

        # Use the first available model for consensus
        first_model = list(self.models)[0]
        consensus_result = self._call_model(first_model, consensus_prompt, max_tokens=1200)

        comparison["consensus"] = consensus_result["output"] if consensus_result["success"] else "Consensus generation failed."
        comparison["consensus_model"] = first_model

        return comparison

    def quick_compare(self, question: str, context: str = None) -> str:
        """
        Simple comparison that returns a formatted string.
        Good for printing directly.
        """
        result = self.consensus(question, context)

        lines = []
        lines.append("=" * 60)
        lines.append(f"  FinSage Multi-Model Analysis")
        lines.append(f"  Question: {question}")
        lines.append("=" * 60)

        for name, r in result["responses"].items():
            status = "OK" if r["success"] else "FAILED"
            lines.append(f"\n--- {name} [{status}] ({r['latency_ms']}ms) ---")
            if r["success"]:
                lines.append(r["output"][:500])
            else:
                lines.append(f"Error: {r['error']}")

        lines.append(f"\n{'=' * 60}")
        lines.append("  CONSENSUS ANALYSIS")
        lines.append(f"{'=' * 60}")
        lines.append(result.get("consensus", "N/A"))

        s = result["summary"]
        lines.append(f"\n--- Stats ---")
        lines.append(f"Models: {s['succeeded']}/{s['total_models']} succeeded")
        if s["fastest_model"]:
            lines.append(f"Fastest: {s['fastest_model']} ({s['fastest_ms']}ms)")
            lines.append(f"Slowest: {s['slowest_model']} ({s['slowest_ms']}ms)")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# Helper: Get context from Snowflake analytics
# ──────────────────────────────────────────────────────────────
def get_ticker_context(ticker: str) -> str:
    """
    Pull analytics context for a ticker from Snowflake.
    Uses the same connection as document_agent.
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    try:
        from snowflake_connection import get_session
        session = get_session()

        # Pull key metrics
        context_parts = []

        # Stock metrics
        try:
            rows = session.sql(f"""
                SELECT CLOSE, DAILY_RETURN_PCT, SMA_7D, SMA_30D, 
                       VOLATILITY_30D_PCT, WEEK_52_HIGH, WEEK_52_LOW, TREND_SIGNAL
                FROM ANALYTICS.FCT_STOCK_METRICS
                WHERE TICKER = '{ticker.upper()}'
                ORDER BY DATE DESC LIMIT 1
            """).collect()
            if rows:
                r = rows[0]
                context_parts.append(
                    f"STOCK: Close=${r['CLOSE']:.2f}, Trend={r['TREND_SIGNAL']}, "
                    f"52w Range=${r['WEEK_52_LOW']:.2f}-${r['WEEK_52_HIGH']:.2f}, "
                    f"Volatility={r['VOLATILITY_30D_PCT']:.2f}%"
                )
        except Exception:
            pass

        # Fundamentals
        try:
            rows = session.sql(f"""
                SELECT REVENUE, NET_INCOME, EPS, REVENUE_GROWTH_YOY_PCT,
                       NET_MARGIN_PCT, FUNDAMENTAL_SIGNAL
                FROM ANALYTICS.FCT_FUNDAMENTALS_GROWTH
                WHERE TICKER = '{ticker.upper()}'
                ORDER BY FISCAL_QUARTER DESC LIMIT 1
            """).collect()
            if rows:
                r = rows[0]
                context_parts.append(
                    f"FUNDAMENTALS: Revenue=${r['REVENUE']:,.0f}, "
                    f"Net Income=${r['NET_INCOME']:,.0f}, EPS=${r['EPS']:.2f}, "
                    f"Revenue Growth YoY={r['REVENUE_GROWTH_YOY_PCT']:.2f}%, "
                    f"Net Margin={r['NET_MARGIN_PCT']:.2f}%, "
                    f"Signal={r['FUNDAMENTAL_SIGNAL']}"
                )
        except Exception:
            pass

        # Sentiment
        try:
            rows = session.sql(f"""
                SELECT SENTIMENT_SCORE, SENTIMENT_LABEL, SENTIMENT_TREND
                FROM ANALYTICS.FCT_NEWS_SENTIMENT_AGG
                WHERE TICKER = '{ticker.upper()}'
                ORDER BY NEWS_DATE DESC LIMIT 1
            """).collect()
            if rows:
                r = rows[0]
                context_parts.append(
                    f"SENTIMENT: Score={r['SENTIMENT_SCORE']:.3f}, "
                    f"Label={r['SENTIMENT_LABEL']}, Trend={r['SENTIMENT_TREND']}"
                )
        except Exception:
            pass

        # SEC financials
        try:
            rows = session.sql(f"""
                SELECT TOTAL_REVENUE, NET_INCOME, OPERATING_MARGIN_PCT,
                       RETURN_ON_EQUITY_PCT, DEBT_TO_EQUITY_RATIO, FINANCIAL_HEALTH
                FROM ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY
                WHERE TICKER = '{ticker.upper()}'
                ORDER BY FISCAL_YEAR DESC LIMIT 1
            """).collect()
            if rows:
                r = rows[0]
                rev = f"${r['TOTAL_REVENUE']:,.0f}" if r['TOTAL_REVENUE'] else "N/A"
                context_parts.append(
                    f"SEC FINANCIALS: Revenue={rev}, "
                    f"ROE={r['RETURN_ON_EQUITY_PCT']}%, "
                    f"D/E={r['DEBT_TO_EQUITY_RATIO']}, "
                    f"Health={r['FINANCIAL_HEALTH']}"
                )
        except Exception:
            pass

        session.close()
        return "\n".join(context_parts) if context_parts else ""

    except Exception as e:
        logger.warning("Could not get Snowflake context: %s", e)
        return ""


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FinSage Multi-Model Comparison")
    parser.add_argument("--question", type=str, required=True,
                        help="Analysis question")
    parser.add_argument("--ticker", type=str, default=None,
                        help="Ticker for analytics context (e.g., AAPL)")
    parser.add_argument("--mode", type=str, choices=["compare", "consensus"],
                        default="consensus",
                        help="compare (raw outputs) or consensus (with synthesis)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    analyzer = MultiModelAnalyzer()

    # Get context if ticker provided
    context = None
    if args.ticker:
        print(f"Loading analytics data for {args.ticker}...")
        context = get_ticker_context(args.ticker)
        if context:
            print(f"Context loaded: {len(context)} chars")
        else:
            print("No context loaded (Snowflake unavailable), proceeding without")

    # Run analysis
    print(analyzer.quick_compare(args.question, context))
