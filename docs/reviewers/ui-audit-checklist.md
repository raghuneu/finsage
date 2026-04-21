# UI Audit Checklist

Systematic UI verification rubric for FinSage. Use this when auditing the stock-viewer UI for visual or functional regressions across multiple tickers.

## Workflow

### Step 1: Select Tickers
- Locate the project's ticker configuration YAML (e.g., `configs/tickers.yaml`)
- Randomly select 5 tickers for the audit
- Record which 5 were selected at the top of the report

### Step 2: Set Up the Audit
- Use Chromium at a consistent viewport (1440x900) for reproducibility
- Create screenshot output directory: `reports/ui-verification/screenshots/`
- Enable full-page screenshots

### Step 3: Systematic UI Traversal

For each selected ticker, navigate through:

**Navigation Structure:**
- Main navigation tabs (Overview, Financials, News, Analysis, etc.)
- Sub-tabs within each main tab
- Every section on each page (headers, tables, charts, cards, metrics)
- Sub-sections and nested components
- Modals, tooltips, dropdowns, interactive elements

**For Each Element, Check:**

1. **Data Accuracy** — Does displayed data match expected values for the ticker?
2. **Data Completeness** — Missing values, empty fields, "N/A" where data should exist, placeholders?
3. **Visual Consistency** — Fonts, colors, spacing, alignment consistent with the design system?
4. **Layout Integrity** — Overflow, broken layouts, misalignment, overlapping components?
5. **Responsiveness** — Does the layout hold at the viewport size?
6. **Loading States** — Stuck loaders, skeletons that never resolve, timeouts?
7. **Error States** — Visible error messages, broken API indicators, console errors?
8. **Interactivity** — Buttons, tabs, filters, dropdowns function correctly?
9. **Charts & Graphs** — Rendering properly, labeled correctly, accurate data ranges?
10. **Typography** — Truncated text, font rendering issues, readability?
11. **Accessibility Basics** — Missing alt text, contrast issues, unlabeled interactive elements?

### Step 4: Capture Screenshots

- Start-of-audit screenshot per ticker (full page)
- Targeted screenshots when an issue is found, named:
  - Format: `{ticker}_{tab_name}_{issue_short_description}.png`
  - Example: `AAPL_financials_missing_revenue_data.png`
- Final overview screenshot per ticker

### Step 5: Generate the Report

**Report Location:** `reports/ui-verification/ui-audit-report-{YYYY-MM-DD}.md`

**Report Structure:**

```
# UI Verification Report
**Date:** {date}
**Tickers Audited:** {list of 5}
**Total Issues Found:** {count}

## Executive Summary
{Overall UI health, most critical issues, patterns observed}

## Audit Results by Ticker

### {Ticker 1} — {Company Name}
**Overall Status:** Pass / Warnings / Fail

#### Tab: {Tab Name}
##### Sub-tab: {Sub-tab Name} (if applicable)
**Section: {Section Name}**
- Pass: {what passed}
- Issue #{n}: {description}
  - **Severity:** Critical / High / Medium / Low
  - **Location:** Exact path (e.g., Financials > Income Statement > Revenue Row)
  - **Expected:** {what should be shown}
  - **Actual:** {what is shown}
  - **Screenshot:** `screenshots/{filename}.png`
  - **Recommendation:** {how to fix}

[Repeat for all tabs, sub-tabs, sections]

[Repeat for all 5 tickers]

## Consolidated Issues List
| # | Ticker | Tab | Section | Issue | Severity | Screenshot |
|---|--------|-----|---------|-------|----------|------------|

## Patterns & Recurring Issues
{Issues appearing across multiple tickers — likely systemic bugs}

## Recommendations
### Critical (Fix Immediately)
### High Priority
### Medium Priority
### Low Priority / Nice to Have

## Audit Coverage Summary
| Ticker | Tabs Checked | Sections Checked | Issues Found | Status |
|--------|-------------|------------------|--------------|--------|
```

## Severity Definitions

- **Critical** — Broken functionality, data not loading, crashes, complete section failure
- **High** — Incorrect data displayed, major visual breakage, key feature not working
- **Medium** — Minor data inconsistencies, visual misalignments, non-critical missing data
- **Low** — Cosmetic issues, minor spacing problems, enhancement suggestions

## Guidelines

1. **Be Exhaustive** — Do not skip any tab, sub-tab, or section
2. **Be Specific** — Always specify exact location, expected vs actual behavior
3. **Screenshot Everything Suspicious** — When in doubt, capture
4. **Don't Assume** — If unsure whether something is a bug or intended, flag as an observation
5. **Track Console Errors** — Note JS errors or network failures observed during navigation
6. **Consistent Navigation** — Same navigation path per ticker for comparable results
7. **Report Passes Too** — Confirm what is working, not just failures
8. **Create the Output Directory** — Ensure `reports/ui-verification/` exists before writing
