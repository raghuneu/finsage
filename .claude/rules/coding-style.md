# Coding Style

## Python Standards

- Follow **PEP 8** conventions
- Use **type annotations** on all function signatures
- Use `snake_case` for functions and variables
- Use `PascalCase` for classes (e.g., `BaseDataLoader`, `ChartAgent`)
- Use `UPPER_SNAKE_CASE` for constants (e.g., `FINSAGE_DB`, `MAX_RETRIES`)

## Core Principles

### KISS (Keep It Simple)
- Prefer the simplest solution that works
- Avoid premature optimization
- Optimize for clarity over cleverness

### DRY (Don't Repeat Yourself)
- Extract repeated logic into shared functions or utilities
- Reuse existing patterns from `src/utils/` and `src/data_loaders/base_loader.py`

### YAGNI (You Aren't Gonna Need It)
- Don't build features or abstractions before they are needed
- Start simple, refactor when the pressure is real

## File Organization

- Functions < 50 lines
- Files < 800 lines (extract into modules when exceeding)
- No deep nesting (> 4 levels) — prefer early returns
- Organize by feature/domain, not by type

## Immutability

Prefer immutable data structures where practical:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TickerConfig:
    symbol: str
    exchange: str
```

## Error Handling

- Handle errors explicitly — never silently swallow exceptions
- Use `try/except` with specific exception types, not bare `except:`
- Provide meaningful error messages that aid debugging
- Log errors with context (ticker, stage, function name)

## Naming Conventions

- Booleans: `is_valid`, `has_data`, `should_retry`
- Functions: verb-noun pattern (`fetch_stock_metrics`, `build_price_summary`, `validate_chart`)
- DataFrames: descriptive (`df_fundamentals`, `df_sentiment`, not just `df`)

## Code Quality Checklist

Before marking work complete:
- [ ] Code is readable and well-named
- [ ] Functions are small (< 50 lines)
- [ ] Files are focused (< 800 lines)
- [ ] No deep nesting (> 4 levels)
- [ ] Proper error handling
- [ ] No hardcoded values (use constants or config)
- [ ] Type annotations on function signatures
