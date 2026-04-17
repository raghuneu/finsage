# Agent Orchestration

## When to Delegate to Subagents

Use specialized subagents for these task patterns:

| Task Type | Action |
|-----------|--------|
| Complex feature request | Use **planner** — create implementation plan first |
| Code written/modified | Use **code-reviewer** — review for quality and security |
| Bug fix or new feature | Use **tdd-guide** — write tests first |
| Security-sensitive code | Use **security-reviewer** — check for vulnerabilities |
| Build/type errors | Use **build-error-resolver** — fix with minimal diffs |
| Architectural decision | Use **architect** — design system structure |

## Parallel Task Execution

ALWAYS use parallel execution for independent operations:

```
# GOOD: Parallel — independent tasks
Agent 1: Review chart_agent.py for security issues
Agent 2: Verify dbt model column names match queries
Agent 3: Run pytest on data loader tests

# BAD: Sequential when unnecessary
First agent 1, wait, then agent 2, wait, then agent 3
```

## FinSage-Specific Agent Patterns

- **Data pipeline debugging**: Trace through RAW → STAGING → ANALYTICS layers, verify column names against `.astro/warehouse.md`
- **Chart agent changes**: Always verify SQL column names against actual Snowflake table schemas before modifying queries
- **dbt model changes**: Run `dbt compile` + `dbt test` after any model modification, then verify downstream consumers (chart_agent.py, analysis_agent.py)
- **Streamlit changes**: Test both the happy path and error states (no data, connection failure, invalid ticker)
