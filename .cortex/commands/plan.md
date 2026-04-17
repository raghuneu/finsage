---
description: Create a phased implementation plan before writing code
---

# Plan

Invoke the planner agent to analyze requirements and create a structured implementation plan before writing any code.

## Steps

1. **Analyze the request** — What is being asked? What are the inputs and outputs?

2. **Search the codebase** for existing patterns:
   - Check `src/data_loaders/` for loader patterns
   - Check `agents/` for agent patterns
   - Check `dbt_finsage/models/` for model patterns
   - Check `frontend/pages/` for page patterns
   - Check `tests/` for testing patterns

3. **Map dependencies** across subsystems:
   - Which Snowflake tables are involved?
   - Which dbt models need changes?
   - Which agents consume the affected data?
   - Which Streamlit pages display the data?

4. **Create a phased plan** with:
   - Exact file paths for each change
   - Dependencies between phases
   - Risk assessment and mitigations
   - Verification steps per phase

5. **Present the plan** and wait for explicit user approval before proceeding to implementation.

## Example

```
User: Add a new data source for insider trading data

Plan:
Phase 1 — Snowflake schema
  - Create RAW_INSIDER_TRADES table
  - Add stg_insider_trades.sql staging view
  - Add fct_insider_activity.sql analytics table

Phase 2 — Data loader
  - Create src/data_loaders/insider_loader.py (extends BaseDataLoader)
  - Add to pipeline orchestration

Phase 3 — Agent integration
  - Add fetch_insider_data() to chart_agent.py
  - Add insider analysis to analysis_agent.py

Phase 4 — Frontend
  - Add Insider Trading page to frontend/

Phase 5 — Testing
  - Create tests/test_insider_loader.py
  - Add dbt tests for new models
```
