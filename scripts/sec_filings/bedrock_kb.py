"""
FinSage Bedrock Knowledge Base Client.

Provides RAG (Retrieval Augmented Generation) over SEC filing text
stored in S3 and indexed by Amazon Bedrock Knowledge Bases.

Usage:
    from sec_filings.bedrock_kb import BedrockKB

    kb = BedrockKB()
    answer = kb.ask("What are Apple's main risks?")
    chunks = kb.retrieve("revenue growth drivers", ticker="AAPL")
    result = kb.cross_ticker_analysis("How do companies discuss AI?")
"""

import os
import json
import logging
from typing import Optional

import boto3
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class BedrockKB:
    """Client for querying FinSage's Bedrock Knowledge Base."""

    def __init__(self, knowledge_base_id=None, region=None, model_id=None):
        self.kb_id = knowledge_base_id or os.getenv("BEDROCK_KB_ID")
        if not self.kb_id:
            raise ValueError("Set BEDROCK_KB_ID in .env")

        self.region = region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.model_id = model_id or os.getenv(
            "BEDROCK_MODEL_ID", "meta.llama3-8b-instruct-v1:0"
        )
        self.model_arn = f"arn:aws:bedrock:{self.region}::foundation-model/{self.model_id}"

        self.client = boto3.client("bedrock-agent-runtime", region_name=self.region)
        self.bedrock_runtime = boto3.client("bedrock-runtime", region_name=self.region)

        logger.info("BedrockKB initialized: kb_id=%s, model=%s", self.kb_id, self.model_id)

    def retrieve(self, query: str, ticker: str = None, max_results: int = 5) -> list:
        """Retrieve relevant text chunks from the Knowledge Base."""
        # Prepend ticker to query for relevance filtering
        search_query = f"{ticker.upper()} {query}" if ticker else query

        # Request extra results when filtering by ticker, since some chunks
        # may belong to other companies and will be dropped.
        fetch_count = max_results * 3 if ticker else max_results

        response = self.client.retrieve(
            knowledgeBaseId=self.kb_id,
            retrievalQuery={"text": search_query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": fetch_count}
            },
        )

        chunks = []
        for result in response.get("retrievalResults", []):
            s3_uri = result.get("location", {}).get("s3Location", {}).get("uri", "")

            # Parse ticker and section from S3 key
            parsed_ticker, section = "", ""
            if s3_uri:
                parts = s3_uri.split("/")
                for i, part in enumerate(parts):
                    if part == "extracted" and i + 1 < len(parts):
                        parsed_ticker = parts[i + 1]
                if s3_uri.endswith("_mda.txt"):
                    section = "MD&A"
                elif s3_uri.endswith("_risk.txt"):
                    section = "Risk Factors"

            chunks.append({
                "text": result.get("content", {}).get("text", ""),
                "score": result.get("score", 0),
                "source": s3_uri,
                "ticker": parsed_ticker,
                "section": section,
            })

        # Post-retrieval ticker filter: drop chunks from other companies
        if ticker:
            target = ticker.upper()
            before = len(chunks)
            chunks = [c for c in chunks if not c["ticker"] or c["ticker"].upper() == target]
            chunks = chunks[:max_results]
            if before != len(chunks):
                logger.info(
                    "Ticker filter: kept %d/%d chunks for %s", len(chunks), before, target
                )

        logger.info("Retrieved %d chunks for: '%s'", len(chunks), search_query[:50])
        return chunks

    def ask(self, question, ticker=None, system_prompt=None):
        """Full RAG: retrieve relevant chunks and generate an answer."""
        if system_prompt is None:
            system_prompt = (
                "You are a senior financial analyst at FinSage. "
                "Answer based ONLY on the SEC filing data provided. "
                "Be specific with numbers and cite which filing your info comes from."
            )

        # Prepend ticker to question for better retrieval
        search_question = f"{ticker.upper()} {question}" if ticker else question

        try:
            response = self.client.retrieve_and_generate(
                input={"text": search_question},
                retrieveAndGenerateConfiguration={
                    "type": "KNOWLEDGE_BASE",
                    "knowledgeBaseConfiguration": {
                        "knowledgeBaseId": self.kb_id,
                        "modelArn": self.model_arn,
                    },
                },
            )
        except Exception as e:
            logger.error("retrieve_and_generate failed: %s", e)
            raise

        answer = response.get("output", {}).get("text", "")

        citations = []
        for citation in response.get("citations", []):
            for ref in citation.get("retrievedReferences", []):
                s3_uri = ref.get("location", {}).get("s3Location", {}).get("uri", "")
                citations.append({
                    "source": s3_uri,
                    "text_snippet": ref.get("content", {}).get("text", "")[:200],
                })

        logger.info("Generated answer with %d citations", len(citations))

        return {
            "answer": answer,
            "citations": citations,
            "model": self.model_id,
        }

    def cross_ticker_analysis(self, question, tickers=None):
        """Analyze a topic across multiple tickers."""
        all_chunks = self.retrieve(question, ticker=None, max_results=10)

        # Group by ticker
        per_ticker = {}
        for chunk in all_chunks:
            t = chunk["ticker"] or "UNKNOWN"
            if tickers and t not in [x.upper() for x in tickers]:
                continue
            if t not in per_ticker:
                per_ticker[t] = []
            per_ticker[t].append(chunk)

        # Build context
        context_parts = []
        for t, chunks in per_ticker.items():
            chunk_texts = "\n".join(
                f"[{c['section']}] {c['text'][:500]}" for c in chunks
            )
            context_parts.append(f"--- {t} ---\n{chunk_texts}")

        combined_context = "\n\n".join(context_parts)

        prompt = f"""You are a senior financial analyst comparing multiple companies.

SEC FILING DATA BY COMPANY:
{combined_context}

QUESTION: {question}

Provide a comparative analysis:
1. How each company addresses this topic differently
2. Which company has the strongest/weakest position
3. Key similarities and differences
4. Investment implications

Be specific and reference details from each company's filing.
Keep under 500 words."""

        try:
            # Use Llama via Bedrock for generation
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "prompt": f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
                    "max_gen_len": 1500,
                    "temperature": 0.3,
                }),
                contentType="application/json",
            )
            result = json.loads(response["body"].read())
            analysis = result.get("generation", "")
        except Exception as e:
            logger.error("Cross-ticker analysis failed: %s", e)
            analysis = f"Analysis generation failed: {e}"

        return {
            "analysis": analysis,
            "tickers_found": list(per_ticker.keys()),
            "per_ticker_chunks": {t: len(c) for t, c in per_ticker.items()},
            "model": self.model_id,
        }

    def health_check(self):
        """Verify the Knowledge Base is accessible."""
        try:
            results = self.retrieve("test query", max_results=1)
            return {
                "status": "healthy",
                "kb_id": self.kb_id,
                "has_data": len(results) > 0,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FinSage Bedrock KB Client")
    parser.add_argument("--question", type=str, required=True)
    parser.add_argument("--ticker", type=str, default=None)
    parser.add_argument("--mode", type=str,
                        choices=["ask", "retrieve", "cross", "health"],
                        default="ask")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    kb = BedrockKB()

    if args.mode == "health":
        print(json.dumps(kb.health_check(), indent=2))

    elif args.mode == "retrieve":
        chunks = kb.retrieve(args.question, ticker=args.ticker)
        for i, c in enumerate(chunks, 1):
            print(f"\n--- Chunk {i} (score: {c['score']:.3f}) ---")
            print(f"Ticker: {c['ticker']} | Section: {c['section']}")
            print(f"Source: {c['source']}")
            print(c["text"][:300] + "...")

    elif args.mode == "cross":
        result = kb.cross_ticker_analysis(args.question)
        print(f"\nTickers: {result['tickers_found']}")
        print(f"\n{result['analysis']}")

    else:
        result = kb.ask(args.question, ticker=args.ticker)
        print(f"\n{result['answer']}")
        print(f"\n--- Citations ({len(result['citations'])}) ---")
        for c in result["citations"]:
            print(f"  {c['source']}")