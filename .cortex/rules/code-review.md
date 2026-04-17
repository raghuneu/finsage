# Code Review Standards

## When to Review

Mandatory review triggers:
- After writing or modifying Python code
- Before any commit to shared branches
- When Snowflake queries are changed (verify column names)
- When dbt models are modified (check downstream impact)
- When security-sensitive code is changed (auth, credentials, API keys)

## Review Checklist

### Security (CRITICAL)
- Hardcoded credentials or API keys
- SQL injection via unvalidated f-string interpolation
- Secrets leaked in logs or error messages
- `.env` file staged for commit

### Code Quality (HIGH)
- Large functions (> 50 lines)
- Large files (> 800 lines)
- Deep nesting (> 4 levels)
- Missing error handling
- Bare `except:` clauses
- Missing type annotations on public functions
- `print()` statements instead of proper logging
- Dead/commented-out code

### Data Pipeline (HIGH)
- SQL column names not matching actual Snowflake schema
- Missing `try/finally` for Snowpark session cleanup
- Hardcoded tickers instead of using `config/tickers.yaml`
- Missing data validation after DataFrame operations
- dbt model changes without updating downstream consumers

### Performance (MEDIUM)
- Unbounded queries (missing `LIMIT` or `WHERE` clause)
- Loading entire tables when only recent data needed
- Repeated Snowflake queries that could be cached
- Synchronous operations that could be parallelized

## Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| CRITICAL | Security vulnerability or data loss risk | BLOCK — must fix |
| HIGH | Bug or significant quality issue | WARN — should fix |
| MEDIUM | Maintainability concern | INFO — consider fixing |
| LOW | Style or minor suggestion | NOTE — optional |

## Approval Criteria

- **Approve**: No CRITICAL or HIGH issues
- **Warning**: Only HIGH issues (merge with caution)
- **Block**: CRITICAL issues found — must fix before merge
