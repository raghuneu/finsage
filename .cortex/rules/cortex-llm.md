# Cortex LLM/VLM Usage Conventions

Rules for using Snowflake Cortex AI functions and VLM (Vision Language Model) features in FinSage.

## Cortex Functions

### COMPLETE — Text Generation

```sql
SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', prompt) AS result;
```

Rules:
- Always specify the model name explicitly
- Use supported Cortex models (check Snowflake docs for current list)
- Handle NULL returns (model may return NULL on errors)
- Log the model name and response latency for observability
- Set appropriate context length for the prompt

### SUMMARIZE — Text Summarization

```sql
SELECT SNOWFLAKE.CORTEX.SUMMARIZE(text_column) AS summary;
```

Rules:
- Input text must be **under 40,000 characters** — truncate or chunk longer texts
- Used in dbt staging models for SEC filing summarization
- Always check for NULL output (indicates input too long or invalid)

### SENTIMENT — Sentiment Analysis

```sql
SELECT SNOWFLAKE.CORTEX.SENTIMENT(text_column) AS score;
```

Rules:
- Returns a FLOAT between -1.0 (negative) and 1.0 (positive)
- Do NOT treat as a string — it's a numeric value
- Used in `stg_news.sql` to enrich raw news data
- Map to categorical labels in analytics layer:
  - \> 0.2 → BULLISH
  - < -0.2 → BEARISH
  - Otherwise → NEUTRAL

## VLM (Vision Language Model) Usage

### Vision Critique Pattern

Used in `agents/vision_utils.py` for chart evaluation:

```python
def vision_critique(image_path: str, chart_type: str) -> CritiqueResult:
    """Evaluate a chart image using VLM."""
```

Rules:
- Maximum 2 refinement iterations per chart
- Always have fallback code (deterministic, no LLM) for when VLM fails
- Log VLM critique results at INFO level
- Handle 3-tier fallback: primary VLM → secondary VLM → text-only critique
- Thread-safe stage creation for parallel chart validation

### VLM Refinement Loop

```python
for iteration in range(MAX_VLM_ITERATIONS):
    code = generate_code(feedback)
    result = execute_code(code)
    if result.success:
        critique = vision_critique(result.image)
        if critique.passes:
            break
        feedback = critique.feedback
```

Rules:
- `MAX_VLM_ITERATIONS = 2` — do not increase without explicit approval
- Always log iteration count and whether fallback was used
- Fallback code must be tested independently (no LLM dependency)

## Bedrock Integration

### Knowledge Base RAG

Rules:
- Always apply Bedrock Guardrails to LLM outputs
- Verify guardrail status in response (check for BLOCKED/FILTERED)
- Log retrieval source passages for auditability
- Use `top_k` parameter to control retrieval depth (default: 5)

### Guardrails

Rules:
- Content safety guardrails must be active for all user-facing outputs
- Grounding checks must be enabled when RAG is used
- If guardrails block a response, log the reason and return a safe fallback message
- Never disable guardrails to "make things work"

### Multi-Model Comparison

Rules:
- Use for consensus validation, not as primary inference
- Log outputs from all models for comparison
- Do not average or blend outputs — use structured voting or majority logic

## Observability

Every LLM/VLM call should log:

```python
logger.info(
    "LLM call completed",
    extra={
        "model": model_name,
        "function": "COMPLETE|SUMMARIZE|SENTIMENT",
        "input_length": len(prompt),
        "output_length": len(result),
        "latency_ms": elapsed_ms,
        "ticker": ticker,
        "success": True
    }
)
```

## Cost Awareness

- Cortex functions consume Snowflake credits
- Avoid calling COMPLETE/SUMMARIZE in loops over large datasets
- Use SENTIMENT in batch SQL (set-based) rather than row-by-row Python calls
- Cache LLM results when the same prompt is repeated (e.g., same ticker analysis within a pipeline run)
