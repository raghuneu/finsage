---
description: Run a comprehensive code review on local changes or a pull request
argument-hint: "[PR number or 'local' for uncommitted changes]"
---

# Code Review

## Usage

```
/code-review local     # Review uncommitted changes
/code-review 42        # Review PR #42
```

## Local Review Mode

1. **Gather changes**:
   ```bash
   git diff --name-only
   git diff --staged --name-only
   ```

2. **Read each changed file** and apply the FinSage review checklist:

### Security Checks
- [ ] No hardcoded credentials (check for API keys, passwords, connection strings)
- [ ] SQL queries use parameterized inputs (no f-string interpolation with user data)
- [ ] Streamlit inputs validated with `sanitize_ticker()` before database queries
- [ ] No `eval()`, `exec()`, or `shell=True` with user input
- [ ] Run `bandit -r` on changed files

### Data Pipeline Checks
- [ ] Data loaders extend `BaseDataLoader` correctly
- [ ] `calculate_quality_score()` returns 0-100
- [ ] External API calls have rate limiting
- [ ] Retry logic uses `tenacity`, not manual loops
- [ ] Tickers read from `config/tickers.yaml`, not hardcoded

### Snowflake Checks
- [ ] Column names are UPPER_SNAKE_CASE
- [ ] Column names verified against `.astro/warehouse.md`
- [ ] Queries include `WHERE TICKER = ...` filter
- [ ] Snowpark sessions closed in `finally` block
- [ ] MERGE keys match table's natural key

### Agent Checks
- [ ] Uses `logging.getLogger(__name__)`, not `print()`
- [ ] LLM calls have timeout handling
- [ ] VLM refinement has fallback path
- [ ] Subprocess calls have explicit timeout

### dbt Checks
- [ ] Model compiles: `dbt compile --select <model>`
- [ ] Tests pass: `dbt test --select <model>`
- [ ] Downstream consumers verified

3. **Generate review report** with severity table (CRITICAL/HIGH/MEDIUM/LOW)

4. **Verdict**: APPROVE if no CRITICAL/HIGH issues, REQUEST CHANGES otherwise

## PR Review Mode

1. **Fetch PR details**:
   ```bash
   gh pr view $PR_NUMBER --json title,body,files,commits
   gh pr diff $PR_NUMBER
   ```

2. **Analyze all changed files** (not just the latest commit — review the full diff)

3. **Apply the same checklist** as local review

4. **Check CI status**:
   ```bash
   gh pr checks $PR_NUMBER
   ```

5. **Post review**:
   ```bash
   gh pr review $PR_NUMBER --approve    # or --request-changes
   gh pr review $PR_NUMBER --comment --body "review details"
   ```

## Validation Commands

After review, verify:

```bash
# Python tests
pytest tests/ -v

# dbt build (if dbt files changed)
dbt build

# Security scan
bandit -r src/ agents/ scripts/ frontend/ -ll

# Linting
ruff check src/ agents/ scripts/
```
