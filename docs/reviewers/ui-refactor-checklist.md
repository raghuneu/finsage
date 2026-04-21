# UI Refactor Checklist

Design rubric for iterating on the FinSage frontend (`finsage-project/frontend-react`). Use this when reviewing UI-focused PRs or doing a design pass on the Next.js app.

## Workflow

1. Inspect the current UI at `localhost:3000`
2. Identify improvements (design, layout, theme, components, typography, spacing, UX flows)
3. Refactor relevant files under `frontend-react/`
4. Verify changes by re-inspecting the UI
5. Repeat until the UI meets production-level fintech standards

---

## Design Philosophy for Finance Applications

### Visual Identity
- Sophisticated, dark-first or light-first design system with a clear primary palette (deep navy, slate, or charcoal base; electric blue, emerald green, or gold accent)
- Avoid generic Bootstrap or default Tailwind looks
- Strong typographic hierarchy with a professional font pairing (Inter or DM Sans for UI, DM Mono or JetBrains Mono for numbers/data)
- Subtle gradients, glassmorphism, or frosted-glass effects used sparingly for cards and panels
- Micro-animations and smooth transitions for state changes

### Layout & Structure
- Clean, spacious layout with consistent grid systems
- Sidebar navigation with clear iconography and active states
- Top header/navbar with contextual actions, user profile, and notifications
- Dashboard layout with well-proportioned card grids
- Visual hierarchy: primary content > secondary info > metadata

### Component Design
- Cards: subtle shadows, rounded corners (12–16px), clear internal padding
- Data tables: alternating row colors, sticky headers, sortable columns with visual indicators
- Charts/graphs: consistent color palette with proper legends
- Form inputs: clear focus states, validation feedback, helper text
- Buttons: primary/secondary/destructive variants with hover/active states
- Skeleton loaders for async content
- Empty states with helpful illustrations or icons

### Finance-Specific UX
- Numbers and currency values prominently displayed with proper formatting
- Consistent color semantics: green for positive/gains, red for losses/negative, amber for warnings
- Trend indicators (arrows, sparklines) immediately recognizable
- KPI cards with clear labels, values, and period-over-period comparisons
- Navigation reflects financial workflows: Dashboard → Portfolio → Transactions → Analytics → Settings

### Readability & Accessibility
- WCAG AA contrast ratios minimum
- Consistent spacing scale (4px base unit)
- Body text minimum 14px, metadata 12px
- Clear visual separation between sections via dividers, spacing, or background color shifts

---

## Refactoring Scope

### Theme & Design Tokens
- `tailwind.config.js` or CSS variables — design token system
- Colors, typography scale, spacing, border radius, shadows, z-index scale
- Dark/light mode support

### Global Styles
- `src/index.css` or `src/styles/globals.css` — base resets, font imports, scrollbar styling
- Focus ring styles, selection colors

### Layout Components
- Root layout wrapper, sidebar, header/navbar
- Page container with proper max-width and padding
- Responsive breakpoints

### Page-Level Components
- Dashboard, Portfolio, Transactions, Analytics, Settings pages
- Each page has clear purpose, proper heading hierarchy, logical content flow

### Reusable UI Components
- Card, Button, Badge, Input, Select, Modal, Tooltip, Dropdown
- Data table with sorting, filtering, pagination
- Chart wrappers with consistent theming
- Stat/KPI card components
- Navigation items with icons

### Typography
- Heading styles (h1–h6)
- Body text, captions, labels
- Monospace for financial figures

---

## Inspection Checklist

After each refactor pass, evaluate:

- [ ] Does the color palette feel cohesive and professional?
- [ ] Is the typography hierarchy clear and readable?
- [ ] Are spacing and alignment consistent throughout?
- [ ] Do interactive elements have proper hover/focus/active states?
- [ ] Are financial data points prominently and clearly displayed?
- [ ] Does the layout feel spacious but not wasteful?
- [ ] Are there visual inconsistencies between pages/components?
- [ ] Does the overall design feel original and not generic?
- [ ] Would this pass as a real production fintech application?

---

## Technical Guidelines

- Preserve all existing functionality — change only visual/structural code
- Do not break existing data flows, API calls, or state management
- Customize existing component library patterns (MUI in this project) heavily instead of using defaults
- Prefer CSS custom properties and utility classes over inline styles
- Keep components modular and reusable
- Ensure changes are responsive (mobile, tablet, desktop)
- Comment significant design decisions in code

---

## Iteration Strategy

**Pass 1 — Foundation:** Design tokens, color system, typography, global styles
**Pass 2 — Layout:** Sidebar, header, page containers, grid system
**Pass 3 — Core Components:** Cards, buttons, inputs, badges, tables
**Pass 4 — Pages:** Dashboard, key feature pages, data visualization
**Pass 5 — Polish:** Micro-interactions, transitions, empty states, loading states, edge cases
**Pass 6+ — Refinement:** Address remaining inconsistencies found during inspection

---

## Success Criteria

The refactor is done when:
1. The application has a distinctive, memorable visual identity
2. Every page feels like it belongs to the same design system
3. Financial data is presented with maximum clarity and professionalism
4. The UI would not look out of place alongside products like Robinhood, Stripe Dashboard, Linear, or Vercel
