# Git Workflow

## Commit Message Format

```
<type>: <description>

<optional body>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

Examples:
- `feat: add SEC financial health chart to CAVM pipeline`
- `fix: correct column name mismatches in chart_agent.py`
- `refactor: extract data fetchers from chart_agent into separate module`
- `docs: update CLAUDE.md with warehouse quick reference`
- `test: add unit tests for fetch_fundamentals_growth`

## Branch Naming

- `feature/<description>` for new features
- `fix/<description>` for bug fixes
- `refactor/<description>` for refactoring

## Pull Request Workflow

When creating PRs:
1. Analyze full commit history (not just latest commit)
2. Use `git diff main...HEAD` to see all changes
3. Draft comprehensive PR summary
4. Include test plan with verification steps
5. Push with `-u` flag if new branch

## Pre-Commit Checks

Before committing:
- [ ] All tests pass (`pytest`)
- [ ] dbt models compile (`cd dbt_finsage && dbt compile`)
- [ ] No hardcoded secrets
- [ ] No `print()` debug statements left in production code
- [ ] No `.env` or credentials files staged
