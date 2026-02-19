---
name: frontend
description: Generate high-quality landing pages with anti-slop guardrails and multi-platform support. Creates modern, accessible designs for Zo.space, standalone HTML, and Next.js with professional aesthetics and clear typography hierarchy.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
created: 2026-02-06
last_edited: 2026-02-06
version: 1.0
provenance: frontend-skill-build-D1.1
---

# Frontend Design Skill

A comprehensive frontend design system that generates professional landing pages across multiple platforms. This skill combines design expertise with anti-slop guardrails to create clean, modern interfaces that avoid generic AI aesthetics.

## Input Spectrum

This skill handles a wide spectrum of input detail levels:

### Vibes Only
- **Example**: "a modern SaaS landing page that feels trustworthy"
- **Behavior**: Generate clarifying questions OR apply tasteful defaults
- **Focus**: Mood, industry, target audience

### Colors & Mood
- **Example**: "Healthcare app, calming blues (#2563eb, #1e40af), professional but approachable"
- **Behavior**: Use specified palette as foundation, derive complementary colors
- **Focus**: Brand personality, emotional tone

### Content Provided
- **Example**: Headlines, feature lists, CTAs, product descriptions
- **Behavior**: Design around provided content, suggest improvements
- **Focus**: Information architecture, content hierarchy

### Template Specified
- **Example**: "Use the saas-minimal template with green accent"
- **Behavior**: Load template from `templates/<name>.yaml`, apply customizations
- **Focus**: Template adaptation, brand alignment

## Generation Workflow

### 1. Input Processing
- Analyze input detail level (vibes → template spectrum)
- Detect or ask for target platform (Zo.space, HTML, Next.js)
- Apply context clues from user's environment or previous requests

### 2. Clarification (when needed)
Ask targeted questions for sparse input:
- "What's the primary call-to-action?"
- "Who's your target audience?"
- "Any brand colors or visual references?"
- "What feeling should visitors have?"

### 3. Anti-Slop Verification
Before generating, review `references/anti-patterns.md` and ensure design avoids:
- Generic purple/blue gradients
- Overly symmetrical layouts  
- Stock illustration aesthetic
- Excessive animations
- Poor typography hierarchy
- Generic "startup" messaging

### 4. Multi-Variant Generation
When `--variants N` is requested:
- Generate N distinct design directions
- Vary layout approach, color treatment, typography scale
- Maintain consistent content hierarchy across variants
- Present clear distinctions between approaches

## Platform-Specific Output

### Zo.space (React/Tailwind/Hono)

Create React components that leverage Zo's full-stack capabilities:

```typescript
// Use update_space_route(path, route_type="page", code, public=True)
import { useState } from "react";
import { ArrowRight, Check } from "lucide-react";

export default function LandingPage() {
  const [email, setEmail] = useState("");
  
  return (
    <div className="min-h-screen bg-zinc-50">
      {/* Component content */}
    </div>
  );
}
```

**Technical requirements:**
- Component must be default export React function
- Use Tailwind 4 classes throughout
- Import icons from `lucide-react` only
- Reference uploaded assets via their asset_path
- Handle form state with React hooks when needed
- Use semantic HTML for accessibility

### Standalone HTML

Self-contained HTML files that work immediately:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Page Title</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body>
  <!-- Content with inline Tailwind -->
</body>
</html>
```

**Technical requirements:**
- Use Tailwind CDN (no external CSS files)
- Inline all custom styles within `<style>` tags
- No external dependencies beyond Tailwind CDN
- Should work when opened directly in browser
- Include basic responsive design patterns

### Next.js (App Router)

Modern Next.js components with latest patterns:

```tsx
// app/page.tsx or components
"use client"; // Only if interactivity needed

export default async function LandingPage() {
  return (
    <main className="min-h-screen">
      {/* Component content */}
    </main>
  );
}
```

**Technical requirements:**
- Use App Router conventions
- Include `"use client"` directive only when needed
- Export default async function component
- Follow Next.js 14+ patterns
- Use standard Tailwind classes
- Handle server/client components appropriately

## Template Application

When a template is specified:

### 1. Template Loading
- Load template YAML from `templates/<name>.yaml`
- Parse `layout`, `palette`, `typography`, and `style_notes` sections
- Validate template exists and is well-formed

### 2. Value Application
- Apply color palette to design system
- Use typography scale for headings/body text
- Follow layout constraints (grid, spacing, component arrangement)
- Incorporate style_notes as aesthetic guidance

### 3. Content Integration
- User-provided content takes precedence over template defaults
- Adapt template structure to accommodate content length
- Maintain template's visual character while serving content needs

### 4. Brand Customization
- Allow accent color overrides
- Adapt template patterns to brand voice
- Preserve template's design integrity while personalizing

## Template Capture

When a generated page perfectly captures the aesthetic you want, you can preserve it as a reusable template for future projects.

### When to Capture

Capture a template when:
- The generated page has a distinctive visual character worth reusing
- You find yourself wanting to recreate the same "feel" for other projects
- The page demonstrates a successful aesthetic approach for a specific domain
- The design balances uniqueness with broad applicability

### Analysis Process

To create an accurate template, analyze the generated page systematically:

#### 1. Color Palette Extraction
- Use browser devtools or eyedropper tools to sample exact colors
- Identify the primary brand color, secondary supporting color, and accent color
- Note background, surface, text, and muted text colors
- Verify contrast ratios meet accessibility standards (4.5:1 minimum)

#### 2. Typography Assessment
- Identify font families used for headings and body text
- Note font weights and the typographic scale (tight/normal/loose)
- Observe heading hierarchy and how it creates visual rhythm
- Check line-height and letter-spacing characteristics

#### 3. Layout Pattern Recognition
- Measure or estimate max-width settings
- Assess spacing rhythm between sections (compact/balanced/airy)
- Note border-radius treatment (none/subtle/rounded/pill)
- Identify grid systems and alignment patterns

#### 4. Section Structure Analysis
- List all sections in order of appearance
- Identify the specific variant used for each section type
- Note any unique section combinations or arrangements
- Document content patterns that work well with this structure

#### 5. Aesthetic Essence Capture
- Describe the intangible "feel" in concrete terms
- Note shadow usage, animation styles, interaction patterns
- Identify what makes this template distinctive from others
- Document the emotional impression it creates

### Template Creation Process

#### 1. Start with the Schema
Copy `templates/_TEMPLATE.yaml` as your starting point:
```bash
cp Skills/frontend/templates/_TEMPLATE.yaml Skills/frontend/templates/your-template-name.yaml
```

#### 2. Fill in Structured Fields
- **name**: Use descriptive slug format (e.g., `minimal-saas`, `bold-agency`, `warm-nonprofit`)
- **description**: Write 2-3 sentences explaining use cases and target aesthetic
- **source**: Credit the original page URL or describe the synthesis process
- **created**: Use current date in YYYY-MM-DD format
- **palette**: Fill in all 7 required color values using exact hex codes
- **typography**: Specify fonts, scale, and heading weight
- **layout**: Set max-width, spacing, and border-radius preferences
- **sections**: List all sections with their variants in order

#### 3. Craft Detailed Style Notes
The `style_notes` field is critical for preserving design nuance. Include:

- **Visual characteristics**: Shadows, borders, gradients (or lack thereof)
- **Typography treatment**: Hierarchy approach, text decoration patterns
- **Color usage patterns**: How colors are applied across different elements
- **Spacing philosophy**: Density preferences, rhythm between elements
- **Interactive elements**: Button styles, hover states, link treatments
- **Content density**: How much information fits comfortably
- **Unique design elements**: Anything that sets this template apart
- **Emotional tone**: The feeling users should have when viewing pages using this template

#### 4. Template Naming Conventions

Choose names that immediately convey the aesthetic:

- **Good examples**: `minimal-saas`, `bold-agency`, `warm-nonprofit`, `technical-docs`, `luxury-ecommerce`
- **Avoid generic names**: `template-1`, `blue-theme`, `modern-design`
- **Include context**: Reference the industry or mood when helpful
- **Keep it memorable**: Names you'll recognize months later

#### 5. Validation Check

Before saving, verify your template:
- All required fields are filled with valid values
- Colors use proper hex format (#000000)
- Typography fonts are available (Google Fonts or system fonts)
- Section types and variants exist in the skill's repertoire
- Style notes capture the essence clearly enough for recreation

### Example Capture Process

**Original page**: A meditation app landing page with sage greens and serif typography

**Analysis notes**:
- Color palette: Sage primary (#059669), warm white background (#FFFEF7)
- Typography: Playfair Display headings, Source Serif Pro body, loose scale
- Layout: Narrow max-width, airy spacing, subtle rounded corners
- Feel: Calm, premium, trustworthy, organic

**Template creation**:
```yaml
name: calm-wellness
description: |
  Meditation and wellness app template with sage greens and serif typography.
  Creates a premium, organic feeling suitable for mindfulness, therapy,
  and personal development products.
source: Meditation app landing page, adapted for broader wellness market
# ... rest of structured fields
style_notes: |
  Serene, premium aesthetic using sage greens and warm typography.
  Serif fonts create trust and tradition. Generous whitespace suggests
  spaciousness and calm. Rounded elements feel organic and approachable...
```

### Template Library Management

- **Keep it curated**: Only capture truly distinctive templates worth reusing
- **Regular review**: Periodically assess whether older templates still represent best practices
- **Documentation**: Update style_notes if you discover new applications or refinements
- **Sharing**: Templates with broad appeal can become part of the core library

## Design Principles

### Typography Hierarchy
- **H1**: Hero headlines, primary value proposition
- **H2**: Section headers, feature categories  
- **H3**: Feature names, subsection titles
- **Body**: Descriptions, supporting text
- **Small**: Captions, legal text, metadata

### Color Strategy
- **Primary**: Brand color, CTAs, key interactive elements
- **Secondary**: Supporting actions, accents, highlights
- **Neutral**: Text, backgrounds, borders, subtle elements
- **Semantic**: Success, warning, error, info states

### Layout Patterns
- **Hero Section**: Value proposition + primary CTA
- **Features Grid**: 3-4 column grid, icon + title + description
- **Social Proof**: Testimonials, logos, usage stats
- **Pricing**: Clear tiers, feature comparison
- **Footer**: Links, contact, social, legal

### Accessibility Standards
- Sufficient color contrast (4.5:1 minimum)
- Focus indicators for all interactive elements  
- Semantic HTML structure
- Alt text for images
- Keyboard navigation support
- Screen reader friendly markup

## Anti-Slop Guardrails

Reference `references/anti-patterns.md` for comprehensive list. Key avoidances:

### Visual Anti-Patterns
- Generic purple/blue gradient backgrounds
- Symmetrical layouts without visual interest
- Stock illustration aesthetic (geometric shapes, flat characters)
- Excessive drop shadows or gloss effects
- Rainbow color schemes without purpose

### Content Anti-Patterns  
- "Revolutionize your workflow" messaging
- Generic "trusted by thousands" claims
- Excessive exclamation points
- Buzzword-heavy descriptions
- Vague value propositions

### UX Anti-Patterns
- Too many CTAs competing for attention
- Poor information hierarchy
- Tiny touch targets on mobile
- Auto-playing videos or animations
- Pop-ups that interrupt reading flow

## Usage Examples

### Basic Usage
```
Generate a landing page for a project management tool. Clean, professional, focus on team collaboration features.
```

### With Variants
```
Create a SaaS pricing page --variants 3
Colors: #2563eb, #1e40af
Content: Starter ($29), Pro ($99), Enterprise ($299)
```

### Template-Based
```
Use the saas-minimal template for a meditation app
Primary color: #059669 (green)
Target: busy professionals seeking mindfulness
```

### Platform-Specific
```
Generate a Next.js component for our product showcase
Features: AI writing, grammar check, tone analysis
Style: Grammarly-inspired but distinct
```

## Quality Standards

Every generated design should meet:

- **Visual Polish**: Professional appearance, consistent spacing
- **Content Clarity**: Clear value proposition, logical flow
- **Technical Quality**: Valid code, responsive design, accessibility
- **Brand Coherence**: Consistent voice, appropriate aesthetics
- **Performance**: Fast loading, optimized images, clean markup

## Advanced Features

### Responsive Design
- Mobile-first approach with progressive enhancement
- Breakpoint strategy: sm (640px), md (768px), lg (1024px), xl (1280px)
- Touch-friendly interactive elements (min 44px)
- Readable typography at all screen sizes

### Performance Optimization
- Semantic HTML structure for fast parsing
- Efficient CSS with Tailwind utilities
- Optimized images with proper sizing
- Minimal JavaScript for interactivity

### SEO Readiness
- Proper heading hierarchy (H1 → H6)
- Meta descriptions and titles
- Structured data markup when relevant
- Fast loading times
- Mobile-friendly design

This skill transforms design briefs into production-ready landing pages that combine aesthetic appeal with technical excellence and user experience best practices.