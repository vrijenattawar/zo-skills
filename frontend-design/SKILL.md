---
name: frontend-design
description: |
  Create distinctive, production-grade frontend interfaces with high design quality.
  Use this skill when building web components, pages, dashboards, or applications.
  Generates creative, polished code that avoids generic AI aesthetics.
compatibility: Created for Zo Computer
metadata:
  author: n5os-ode
---

# Frontend Design

Build web interfaces that look like a human designer made them, not an AI. This skill enforces intentional aesthetic choices, proper typography hierarchy, and deliberate color systems to produce production-grade frontend code.

## Design Thinking

Before writing any code, answer these questions:

1. **What is the purpose?** — What is the user trying to accomplish? What emotion or response should the interface evoke? (Trust? Excitement? Calm efficiency?)

2. **Pick a bold aesthetic direction** — Choose a specific visual identity. Examples:
   - Dark editorial (high contrast, serif headlines, generous whitespace)
   - Warm minimal (earth tones, rounded corners, soft shadows)
   - Technical precision (monospace accents, grid-heavy, data-forward)
   - Playful conversational (hand-drawn feel, bright accents, informal type)

3. **Identify constraints** — Viewport targets, accessibility needs, brand guidelines, performance budgets, framework requirements.

4. **Find differentiation** — What makes this interface *not* look like every other AI-generated page? At least one element should be unexpected or distinctive.

---

## Anti-Slop Checklist

Before shipping, verify none of these appear:

### Banned Defaults

- [ ] **No default blue (`#3b82f6`)** — If you need blue, choose a specific shade with intention (slate blue, electric blue, navy). Never use Tailwind's `blue-500` without customization.
- [ ] **No generic gradients** — `bg-gradient-to-r from-blue-500 to-purple-600` is the hallmark of AI-generated UI. If using gradients, make them subtle and purposeful.
- [ ] **No "Hero → Features Grid → CTA" template** — This is the most common AI layout. Break the pattern: lead with a story, use asymmetric layouts, or let content dictate structure.
- [ ] **No Lorem Ipsum** — Every piece of text should be real or clearly marked as placeholder with context (e.g., "[Company tagline — 6-8 words]").
- [ ] **No decorative emojis as design elements** — Emojis are content, not decoration. Use proper icons (Lucide, Heroicons) or custom SVG.
- [ ] **No centered-everything layouts** — Left-aligned text is easier to read. Center-align only headlines and short CTAs.
- [ ] **No identical card grids** — If showing multiple items, vary the presentation (featured item larger, alternating layouts, editorial list style).

---

## Typography Hierarchy

Establish a clear type scale. Every level should be visually distinct at a glance.

| Level | Role | Size Range | Weight | Notes |
|-------|------|-----------|--------|-------|
| Display | Hero headlines, page titles | 48–72px | 700–900 | Use sparingly, one per page max |
| Heading | Section titles | 28–36px | 600–700 | Clear contrast from body text |
| Subheading | Subsection labels, card titles | 20–24px | 500–600 | Bridges heading and body |
| Body | Paragraphs, descriptions | 16–18px | 400 | Optimize for readability, 1.5–1.75 line height |
| Caption | Labels, metadata, timestamps | 12–14px | 400–500 | Lighter color or reduced opacity for visual hierarchy |

### Type Rules

- **Maximum two typefaces** — One for headings, one for body. Or one typeface at different weights.
- **Line length**: 50–75 characters per line for body text. Use `max-w-prose` or equivalent.
- **Vertical rhythm**: Maintain consistent spacing between type levels. Heading margin-bottom should relate to body line-height.

---

## Color System

### Structure

- **2–3 primary colors maximum** — One dominant, one secondary, one accent. Adding more dilutes the visual identity.
- **Neutral palette** — Build from a tinted neutral (warm gray, cool slate, olive) rather than pure gray. Pure `#gray` feels flat.
- **Semantic colors** — Success, warning, error, info. These should harmonize with your primary palette, not use default green/yellow/red/blue.

### Contrast Requirements

- Body text on background: minimum 4.5:1 contrast ratio (WCAG AA)
- Large text (>18px bold or >24px): minimum 3:1
- Interactive elements: clearly distinguished from static content
- Hover/focus states: visible change in at least one property (color, shadow, border, scale)

### Accent Usage

- Accent color should appear on 5–15% of the visible surface
- Use for: primary CTAs, active states, key data points, navigation indicators
- Never use accent as a background for large areas

---

## Layout Principles

### Whitespace

- **More than you think** — The most common amateur mistake is insufficient spacing. When in doubt, add more padding.
- **Consistent spacing scale** — Use a base unit (4px or 8px) and multiply. Common scale: 4, 8, 12, 16, 24, 32, 48, 64, 96.
- **Section breathing room** — Major sections need 64–128px vertical padding. This is not wasted space; it is structure.

### Visual Rhythm

- **Vary element sizes** — Not every card should be the same size. Not every section should be the same height. Monotony is the enemy of engagement.
- **Create focal points** — Each viewport should have one dominant element that draws the eye first. Use size, color, or position contrast.
- **Asymmetry with intent** — Perfectly centered, perfectly symmetric layouts feel static. Introduce controlled asymmetry (offset headings, unequal column widths, varied card sizes).

### Responsive Design

- **Design for content, not breakpoints** — Let content determine where the layout needs to adapt, rather than forcing arbitrary breakpoints.
- **Mobile is not "desktop but smaller"** — Reconsider information hierarchy for small screens. What matters most on mobile may differ from desktop.
- **Touch targets** — Minimum 44×44px for interactive elements on touch devices.

---

## Banned Patterns

These specific patterns are overused in AI-generated interfaces and should be avoided or significantly reimagined:

| Pattern | Problem | Alternative |
|---------|---------|-------------|
| 3-column equal card grid | Every AI page has this | Vary card sizes, use masonry, editorial list, or featured+grid |
| Gradient background header | Screams "template" | Solid color, image, pattern, or color block composition |
| Rounded avatar + name + title card | Generic "team section" | Photo collage, editorial bios, interactive profiles |
| Icon + heading + paragraph (×6) | Default "features" section | Show, don't tell: use screenshots, demos, or stories |
| Full-width centered everything | Lacks visual hierarchy | Left-aligned content areas with intentional whitespace |
| Shadow-everything | Over-decorated | Use shadows sparingly for elevation hierarchy only |

---

## Platform Guidance

### Zo.space (React + Tailwind)

- Routes are single-file React components with Tailwind CSS 4
- `lucide-react` available for icons
- Use `useState`, `useEffect` for interactivity
- Tailwind classes for all styling — no external CSS files
- Reference assets with absolute paths (`/images/...`)

### Standalone HTML

- Single-file delivery: inline CSS in `<style>`, inline JS in `<script>`
- Use CSS custom properties for theming
- Prefer modern CSS (grid, flexbox, clamp, container queries) over frameworks
- Include viewport meta tag and minimal reset

### Next.js

- Component-based architecture with proper file structure
- Use CSS Modules, Tailwind, or styled-components consistently (pick one)
- Server components by default, client components only when needed
- Image optimization via `next/image`
- Font optimization via `next/font`
