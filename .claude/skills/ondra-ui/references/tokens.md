# Tokens

Tailwind v4, CSS-first. Tokens live in one `@theme` block. Until `packages/ui` exists, `apps/site/app/globals.css` is the source of truth; when `apps/web` starts, move the block to `packages/ui/styles/tokens.css` and import it from both apps (`@source "../../../packages/ui"`).

## Colour

| Token | Value | Role | Contrast that matters |
|---|---|---|---|
| `ink` | `#16171B` | Text, dark sections, sidebar | 15.6:1 on Paper |
| `ink-2` | `#2A2C32` | Secondary text on Paper, raised dark surfaces | |
| `muted-foreground` | `#5F626A` | Tertiary text, captions | 5.0:1 on Paper. The old `#6B6E76` was 4.44:1 and fails AA for small text |
| `muted` | `#ECEAE5` | Quiet surface (skeletons, tracks, secondary buttons) | shadcn meaning: `muted` is a surface, `muted-foreground` is text. Never `text-muted` |
| `paper` | `#F1EFEA` | Page background | |
| `paper-2` | `#E7E4DD` | Second neutral: sidebars, panels, alternating bands | |
| `line` | `#DCD8CF` | Borders, dividers | |
| `sodium` | `#F2A33A` | Primary action fill, active state | Ink on it 8.6:1. White on it 2.1:1 (never) |
| `sodium-hi` / `sodium-lo` | mixes of sodium | Hover / pressed | |
| `sodium-ink` | `#1A1206` | Text on sodium | |
| `sodium-edge` | `#C27A12` | Amber lines and outlines that must reach 3:1 | 3.45:1 on white |
| `ai` / `ai-bg` | `#1E3F7A` / `#EAF1FF` | Anything the AI did | 9.05:1 |
| `ai-mark` | `#5B8DEF` | AI series in charts, the dot on AI labels | 3.2:1 on white |
| `vip` / `vip-bg` | `#A3191E` / `#FFE9EA` | VIP and overdue only | 6.66:1 |
| `ok` | `#1F6B45` | Positive deltas, "connected" states | 6.5:1 on white |
| `wa` | `#1F7A4D` | WhatsApp channel mark only | |

Rules:
- Drop the default palette (`--color-*: initial;`) so only brand colours exist and stray `bg-purple-500` fails to compile.
- Alpha comes free: `bg-ink/60` compiles to `color-mix`. Do not store RGB triplets.
- Derive hover and tint shades with `color-mix(in oklab, …)`, not hand-picked hexes.
- On coloured surfaces, derive secondary text from the surface (e.g. `text-paper/70` on Ink), not from a grey.
- Focus ring: 2px Ink outline, 2px offset on light surfaces; 2px sodium on Ink surfaces (8.6:1).
- Dark mode: not on `apps/site` (it is a fixed editorial design). In `apps/web`, only if planned, and composed, never mechanically inverted. Class toggle: `@custom-variant dark (&:where(.dark, .dark *));`.

## Type

```css
--font-sans: "Archivo", ui-sans-serif, system-ui, sans-serif;
--font-sans--font-variation-settings: "wdth" 100;
--font-display: "Archivo", ui-sans-serif, system-ui, sans-serif;
--font-display--font-variation-settings: "wdth" 125;
```
`font-display` then sets the width itself. Do not hand-write `font-variation-settings` in components.

Scale (each step carries its own line height, tracking and weight):

| Token | Size | Use |
|---|---|---|
| `text-micro` | 12px / 16 | Chart axes, timestamps. Not for body text |
| `text-small` | 14px / 22 | Secondary UI text, table cells in dense views |
| `text-body` | 16px / 26 | Body, inputs, buttons |
| `text-lead` | 18-21px fluid | Section ledes on marketing |
| `text-h4` | 20px / 1.35, 600 | Card titles |
| `text-h3` | 22-28px fluid, 650 | Sub-sections |
| `text-h2` | 28-44px fluid, 700, -0.015em | Section headings |
| `text-h1` | 36-64px fluid, 750, -0.02em | Page titles |
| `text-display` | 44-96px fluid, 800, -0.025em | Marketing hero only |

Fluid sizes belong on marketing. The dashboard uses fixed rem steps (ratio about 1.2): 12, 14, 16, 20, 24, 30.

## Space, shape, elevation

- Spacing multiplier `--spacing: 0.25rem` (4px base). Use the integer utilities (`p-4`, `gap-6`); no named spacing tokens.
- Containers: `--container-prose: 40rem`, `--container-page: 76rem`.
- Radius by role: `rounded-control` 6px (buttons, inputs), `rounded-card` 12px (cards, popovers, floor labels), `rounded-panel` 20px (hero media, device frames), `rounded-pill` only for chips and tags. Nothing else.
- Elevation is declared once per element: a border **or** a shadow, not both. Cards on Paper use a border. Floating things (popovers, floor labels, toasts) use `shadow-float`.
- Control heights: 36 (dense), 44 (default, touch minimum), 52 (marketing CTA).

## Motion

```css
--ease-out-quart: cubic-bezier(0.25, 1, 0.5, 1);   /* UI enters, hover */
--ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);    /* large reveals, sheets, hero */
--ease-in-out-quart: cubic-bezier(0.76, 0, 0.24, 1); /* moves in place, tabs */
--ease-in-quart: cubic-bezier(0.5, 0, 0.75, 0);    /* exits only */
--default-transition-duration: 160ms;
--default-transition-timing-function: var(--ease-out-quart);
```
Durations: 80 press, 160 hover and colour, 240 popovers and chips, 400 dialogs and sheets, 700 maximum (hero only). Exits run at about 70% of the enter time. Animate only `transform`, `opacity`, `clip-path`; `filter: blur` only on small text blocks. One ambient loop per viewport at most, paused off-screen. Reduced motion means fewer and gentler, not a global 1ms kill: keep state feedback, drop travel and loops.

## Browser surfaces

Cheap, and the clearest sign a page was built rather than assembled:
```css
::selection { background: color-mix(in oklab, var(--color-sodium) 45%, transparent); color: var(--color-ink); }
html { caret-color: var(--color-ink); scrollbar-color: var(--color-line) transparent; accent-color: var(--color-sodium); }
a { text-underline-offset: 0.2em; text-decoration-thickness: 1px; }
```
