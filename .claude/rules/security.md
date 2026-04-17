# Security Guidelines

## Mandatory Security Checks

Before ANY commit:
- [ ] No hardcoded secrets (API keys, passwords, tokens, Snowflake credentials)
- [ ] All user inputs validated (Streamlit widgets, CLI args, API parameters)
- [ ] SQL injection prevention (parameterized queries or validated inputs for Snowflake)
- [ ] Error messages don't leak sensitive data (connection strings, internal paths)
- [ ] No secrets in logs or print statements

## Secret Management

- NEVER hardcode secrets in source code
- ALWAYS use `.env` + `python-dotenv` for credentials
- Validate that required env vars are present at startup (fail fast with clear message)
- Snowflake credentials go in `.env` only, never in `profiles.yml` committed to git
- AWS credentials use environment variables or IAM roles, never hardcoded

## Snowflake-Specific Security

- Use parameterized queries where possible; when using f-strings for SQL, validate/sanitize ticker symbols and other user inputs
- Never log full SQL queries that contain sensitive filter values
- Close Snowpark sessions in `finally` blocks to prevent connection leaks
- Verify warehouse/database/schema before executing queries

## Streamlit Security

- Sanitize all `st.text_input()` values before using in SQL or API calls
- Never display raw exception tracebacks to users in production
- Use `st.secrets` or `.env` for credentials, never hardcode in `app.py`

## Static Security Analysis

```bash
# Run bandit for Python security scanning
bandit -r src/ agents/ scripts/ -ll
```

## Security Response Protocol

If a security issue is found:
1. STOP immediately
2. Fix CRITICAL issues before continuing
3. Rotate any exposed secrets
4. Review related code for similar issues
