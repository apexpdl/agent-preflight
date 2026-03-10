# Visual Design Language

## Principles

Preflight's visual identity communicates three things: **infrastructure-grade seriousness**, **technical precision**, and **operational clarity**. It should feel like infrastructure documentation, not a marketing site.

---

## Tone

- Serious. Not playful.
- Precise. Not vague.
- Calm. Not urgent or alarmist.
- Grounded. Not aspirational.

Write like you are documenting a production system that people depend on. Avoid startup cliches, buzzword stacking, and over-marketing.

---

## Typography

### Primary

- **Monospace** for all code, configurations, and technical content: `JetBrains Mono`, `Fira Code`, or `Source Code Pro`
- **Sans-serif** for headings and body text: `Inter`, `IBM Plex Sans`, or system defaults

### Hierarchy

- H1: Used once per page. Bold, large.
- H2: Section headers. Clear and scannable.
- H3: Subsection headers.
- Body: Concise sentences. Short paragraphs.
- Code: Always in fenced blocks with language specifiers.

### Rules

- No italic for emphasis. Use **bold** sparingly.
- No ALL CAPS except in code constants and enum values.
- No exclamation marks in documentation.

---

## Color Palette

### Core

| Name | Hex | Usage |
|---|---|---|
| Background | `#0a0a0f` | Page background, dark theme |
| Surface | `#12121a` | Cards, panels |
| Border | `#1e1e2e` | Borders, dividers |
| Text Primary | `#e2e2e8` | Body text, headings |
| Text Secondary | `#7a7a8e` | Labels, captions, metadata |

### Semantic

| Name | Hex | Usage |
|---|---|---|
| Allow | `#22c55e` | ALLOW verdicts, low risk, success states |
| Warn | `#eab308` | WARN verdicts, medium risk, caution states |
| Block | `#ef4444` | BLOCK verdicts, high risk, error states |
| Info | `#3b82f6` | Informational, links, passive actions |

### Rules

- No gradients in UI or documentation.
- No neon or "AI-style" color effects.
- Color is used functionally (verdicts, risk levels), never decoratively.
- Dark theme is the primary presentation. Light theme is optional.

---

## Diagrams

### Style

- Use ASCII art for README diagrams (universal rendering).
- Use Mermaid for documentation pages (ARCHITECTURE.md, etc.).
- Diagrams should be left-aligned, not centered.
- Use clear labels. No abbreviations without context.

### Pipeline Diagrams

The governance pipeline should always flow top-to-bottom:

```
Input -> Stage 1 -> Stage 2 -> ... -> Verdict -> Output
```

### Architecture Diagrams

System architecture should flow left-to-right:

```
Agent -> Preflight -> [Pipeline stages] -> Production
```

### Rules

- No icons or logos in diagrams.
- No rounded boxes or decorative elements.
- Straight lines, right angles.
- Every box must have a clear label.

---

## Icons

- No emojis in any documentation, code comments, or UI.
- Use text-based indicators for status:
  - `[ALLOW]` / `[WARN]` / `[BLOCK]`
  - `[x]` for completed, `[ ]` for pending
- Shield badges (build, coverage, license) are acceptable in the README header only.

---

## Documentation Structure

### Page Template

```markdown
# Title

One-line description.

---

## Section

Content.

### Subsection

Content.
```

### Rules

- Every page starts with a single H1 and a one-line description.
- Use horizontal rules (`---`) between major sections.
- Tables are preferred over bullet lists for structured data.
- Code examples are complete and runnable, not fragments.

---

## What to Avoid

- Playful emojis or emoji-heavy section markers
- Phrases like "supercharge", "turbocharge", "unleash", "game-changing"
- Generic AI gradient imagery
- Marketing language in technical documentation
- Passive voice in descriptions of system behavior
- Vague statements without concrete examples
