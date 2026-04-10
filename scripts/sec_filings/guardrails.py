"""
FinSage Bedrock Guardrails Integration.

Applies guardrails to all Bedrock LLM calls to:
  - Detect hallucinations (contextual grounding)
  - Block investment advice (denied topics)
  - Redact PII (sensitive information filters)
  - Filter harmful content

Usage:
    from sec_filings.guardrails import GuardedLLM

    llm = GuardedLLM()

    # Safe generation with guardrails
    result = llm.generate("Analyze Apple's financials", context="...")
    print(result["output"])
    print(result["guardrail_action"])  # NONE, GUARDRAIL_INTERVENED

    # Apply guardrails to existing text (no model call)
    check = llm.check_output("Buy AAPL now, it will hit $500!")
    print(check["action"])  # GUARDRAIL_INTERVENED
"""

import os
import json
import logging
from typing import Optional

import boto3
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GuardedLLM:
    """Bedrock LLM client with Guardrails applied to every call."""

    def __init__(self, guardrail_id=None, guardrail_version=None,
                 model_id=None, region=None):
        self.guardrail_id = guardrail_id or os.getenv("BEDROCK_GUARDRAIL_ID")
        self.guardrail_version = guardrail_version or os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "meta.llama3-8b-instruct-v1:0")
        self.region = region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")

        if not self.guardrail_id:
            raise ValueError("Set BEDROCK_GUARDRAIL_ID in .env")

        self.client = boto3.client("bedrock-runtime", region_name=self.region)

        logger.info(
            "GuardedLLM initialized: guardrail=%s (v%s), model=%s",
            self.guardrail_id, self.guardrail_version, self.model_id
        )

    def generate(self, prompt: str, context: str = None,
                 max_tokens: int = 1500) -> dict:
        """
        Generate a response with guardrails applied.

        Args:
            prompt: The user question or instruction
            context: Source text for grounding check (e.g., SEC filing text)
            max_tokens: Maximum response length

        Returns:
            dict with 'output', 'guardrail_action', 'blocked', 'trace'
        """
        # Build messages
        messages = [{"role": "user", "content": [{"text": prompt}]}]

        # If context provided, add it as system prompt for grounding
        system = []
        if context:
            system = [{
                "text": (
                    "You are a senior financial analyst at FinSage. "
                    "Answer based ONLY on the following source data. "
                    "Do not make up numbers or facts not in the source.\n\n"
                    f"SOURCE DATA:\n{context[:30000]}"
                )
            }]

        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=messages,
                system=system,
                guardrailConfig={
                    "guardrailIdentifier": self.guardrail_id,
                    "guardrailVersion": self.guardrail_version,
                    "trace": "enabled",
                },
                inferenceConfig={"maxTokens": max_tokens, "temperature": 0.3},
            )

            # Extract output
            output_text = ""
            for block in response.get("output", {}).get("message", {}).get("content", []):
                if "text" in block:
                    output_text += block["text"]

            # Check guardrail action
            stop_reason = response.get("stopReason", "")
            guardrail_action = "NONE"
            blocked = False

            if stop_reason == "guardrail_intervened":
                guardrail_action = "GUARDRAIL_INTERVENED"
                blocked = True
                logger.warning("Guardrail intervened on response")

            # Extract trace info
            trace = response.get("trace", {}).get("guardrail", {})
            trace_summary = self._parse_trace(trace)

            return {
                "output": output_text,
                "guardrail_action": guardrail_action,
                "blocked": blocked,
                "stop_reason": stop_reason,
                "trace_summary": trace_summary,
                "model": self.model_id,
            }

        except Exception as e:
            logger.error("GuardedLLM generate failed: %s", e)
            raise

    def check_output(self, text: str, source: str = None) -> dict:
        """
        Check text against guardrails WITHOUT calling a model.
        Uses the ApplyGuardrail API.

        Args:
            text: Text to check (e.g., a model response)
            source: Optional source text for grounding check

        Returns:
            dict with 'action', 'blocked', 'details'
        """
        content = [{"text": {"text": text}}]

        # Add grounding source if provided
        if source:
            content.append({
                "text": {
                    "text": source,
                    "qualifiers": ["grounding_source"]
                }
            })

        try:
            response = self.client.apply_guardrail(
                guardrailIdentifier=self.guardrail_id,
                guardrailVersion=self.guardrail_version,
                source="OUTPUT",
                content=content,
            )

            action = response.get("action", "NONE")
            blocked = action == "GUARDRAIL_INTERVENED"

            # Parse assessments
            details = []
            for assessment in response.get("assessments", []):
                # Content filter results
                for cf in assessment.get("contentPolicy", {}).get("filters", []):
                    if cf.get("action") == "BLOCKED":
                        details.append(f"Content blocked: {cf.get('type')} ({cf.get('confidence')})")

                # Topic results
                for topic in assessment.get("topicPolicy", {}).get("topics", []):
                    if topic.get("action") == "BLOCKED":
                        details.append(f"Denied topic: {topic.get('name')}")

                # PII results
                for pii in assessment.get("sensitiveInformationPolicy", {}).get("piiEntities", []):
                    if pii.get("action") == "ANONYMIZED":
                        details.append(f"PII masked: {pii.get('type')}")

                # Grounding results
                grounding = assessment.get("contextualGroundingPolicy", {})
                for filter_result in grounding.get("filters", []):
                    score = filter_result.get("score", 0)
                    threshold = filter_result.get("threshold", 0)
                    filter_type = filter_result.get("type", "")
                    if filter_result.get("action") == "BLOCKED":
                        details.append(
                            f"Grounding failed: {filter_type} "
                            f"(score={score:.2f}, threshold={threshold:.2f})"
                        )

            logger.info("Guardrail check: action=%s, details=%s", action, details)

            return {
                "action": action,
                "blocked": blocked,
                "details": details,
                "output": response["outputs"][0].get("text", text) if response.get("outputs") else text,
            }

        except Exception as e:
            logger.error("Guardrail check failed: %s", e)
            return {
                "action": "ERROR",
                "blocked": False,
                "details": [str(e)],
                "output": text,
            }

    def _parse_trace(self, trace: dict) -> list:
        """Parse guardrail trace into human-readable summary."""
        summary = []

        input_assessment = trace.get("inputAssessment", {})
        output_assessments = trace.get("outputAssessments", [])

        # Check input
        for topic in input_assessment.get("topicPolicy", {}).get("topics", []):
            if topic.get("action") == "BLOCKED":
                summary.append(f"INPUT blocked: denied topic '{topic.get('name')}'")

        # Check outputs
        for assessment in output_assessments:
            for topic in assessment.get("topicPolicy", {}).get("topics", []):
                if topic.get("action") == "BLOCKED":
                    summary.append(f"OUTPUT blocked: denied topic '{topic.get('name')}'")

            for pii in assessment.get("sensitiveInformationPolicy", {}).get("piiEntities", []):
                summary.append(f"PII masked: {pii.get('type')}")

            grounding = assessment.get("contextualGroundingPolicy", {})
            for f in grounding.get("filters", []):
                if f.get("action") == "BLOCKED":
                    summary.append(
                        f"Grounding failed: {f.get('type')} "
                        f"(score={f.get('score', 0):.2f})"
                    )

        return summary


# ──────────────────────────────────────────────────────────────
# CLI for testing
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FinSage Guardrails Test")
    parser.add_argument("--prompt", type=str, required=True,
                        help="Text to test")
    parser.add_argument("--mode", type=str, choices=["generate", "check"],
                        default="check",
                        help="generate (call model + guardrails) or check (guardrails only)")
    parser.add_argument("--context", type=str, default=None,
                        help="Source text for grounding check")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    llm = GuardedLLM()

    if args.mode == "generate":
        result = llm.generate(args.prompt, context=args.context)
        print(f"\nOutput: {result['output']}")
        print(f"Guardrail Action: {result['guardrail_action']}")
        print(f"Blocked: {result['blocked']}")
        if result['trace_summary']:
            print(f"Trace: {result['trace_summary']}")

    else:
        result = llm.check_output(args.prompt, source=args.context)
        print(f"\nAction: {result['action']}")
        print(f"Blocked: {result['blocked']}")
        if result['details']:
            print(f"Details:")
            for d in result['details']:
                print(f"  - {d}")
        print(f"Output: {result['output'][:300]}")
