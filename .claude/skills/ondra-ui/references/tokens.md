# Tokens

Tailwind v4, CSS-first. Tokens live in one `@theme` block. Until `packages/ui` exists, `apps/site/app/globals.css` is the source of truth; when `apps/web` starts, move the block to `packages/ui/styles/tokens.css` and import it from both apps (`@source "../../../packages/ui"`).

## Colour: Night Shift (dark, the marketing site and the default theme)

| Token | Value | Role | Contrast that matters |
|---|---|---|---|
| `night` | `#06080B` | Deepest ground: hero, key bands, footer, sticky nav | |
| `bg` | `#0A0D12` | Page | |
| `bg-2` | `#0E131A` | Alternating bands | |
| `surface` | `#121822` | Cards, inputs, floating labels | |
| `muted` | `#1A2230` | Quiet chips, skeletons, tracks. A surface, never text | |
| `line` / `line-strong` | `#222C3A` / `#34425A` | Borders, dividers / stronger outlines | |
| `fg` | `#EAF0F7` | Text | 16:1 on bg |
| `fg-2` | `#C3CDDA` | Secondary text | 11:1 |
| `muted-foreground` | `#8E9CB0` | Captions, meta | 6.6:1 on bg |
| `brand` | `#2F6CF6` | Ondra blue fill: marketing CTAs, the logo dot | White on it 4.6:1 |
| `brand-hi` / `brand-lo` | `#4C86FF` / `#2457D6` | Hover / pressed; `brand-hi` is the focus ring | |
| `brand-text` | `#7FA9FF` | Ondra blue as text or icons on dark | 7.4:1 |
| `ai` / `ai-subtle` / `ai-mark` | `#9DBCFF` / `#13203A` / `#4C86FF` | Anything the AI did: text, tinted surface, dots | 8.6:1 |
| `vip` / `vip-subtle` | `#FF7A7A` / `#3A1517` | VIP and overdue only | 6.9:1 |
| `ok` | `#3DD68C` | Positive deltas, connected states, Answer buttons | |
| `wa`, `wa-wallpaper`, `wa-bubble`, `wa-incoming` | `#25D366`, `#0B141A`, `#005C4B`, `#202C33` | WhatsApp mark and dark-mode chat mocks only | |
| `accent` | `#15233D` | Selected list row | |

**Light theme (the dashboard, later):** keep the same roles with these values: `bg #F4F7FA`, `surface #FFFFFF`, `line #E1E6EE`, `fg #0C1220`, `muted-foreground #4E5A6B`, `brand #2F6CF6`, `ai #1F4FD1` on `#E8EEFF`, `vip #B4122B` on `#FDE8EB`. Dealers stare at the dashboard all day, and light is kinder for a 10-hour shift. Compose it; don't invert the dark theme.

Rules:
- Drop the default palette (`--color-*: initial;`) so only brand colours exist and a stray `bg-purple-500` fails to compile.
- Alpha comes free: `bg-night/80` compiles to `color-mix`. Don't store RGB triplets.
- On dark, secondary text is `fg-2` or `muted-foreground`, or `white/70` over imagery. Never grey on blue.
- Focus ring: 2px `brand-hi`, 2px offset.
- No gradients except the dark scrims over imagery. No glows.

## Type

```css
--font-sans: "Funnel Sans Variable", "Funnel Sans", ui-sans-serif, system-ui, sans-serif;
--font-display: "Funnel Display Variable", "Funnel Display", ui-sans-serif, system-ui, sans-serif;
--font-mono: "JetBrains Mono Variable", "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
```
Self-host with `@fontsource-variable/funnel-display`, `@fontsource-variable/funnel-sans` and `@fontsource-variable/jetbrains-mono` (imported in the root layout). There's no third-party font request and no layout shift.

Scale (each step carries its own line height, tracking and weight):

| Token | Size | Use |
|---|---|---|
| `text-micro` | 12px / 16 | Chart axes, timestamps. Not for body text |
| `text-small` | 14px / 22 | Secondary UI text, table cells in dense views |
| `text-body` | 16px / 26 | Body, inputs, buttons |
| `text-lead` | 18-21px fluid | Section ledes on marketing |
| `text-h4` | 20px / 1.35, 600 | Card titles |
| `text-h3` | 22-28px fluid, 650 | Sub-sections |
| `text-h2` | 30-52px fluid, 600, -0.025em | Section headings |
| `text-h1` | 36-64px fluid, 600, -0.03em | Page titles |
| `text-display` | 44-96px fluid, 600, -0.035em | Marketing hero only |

Fluid sizes belong on marketing. The dashboard uses fixed rem steps (ratio about 1.2): 12, 14, 16, 20, 24, 30.

## Space, shape, elevation

- Spacing multiplier `--spacing: 0.25rem` (4px base). Use the integer utilities (`p-4`, `gap-6`); no named spacing tokens.
- Containers: `--container-prose: 40rem`, `--container-page: 76rem`.
- Radius by role: `rounded-control` 6px (buttons, inputs), `rounded-card` 12px (cards, popovers, floor labels), `rounded-panel` 20px (hero media, device frames), `rounded-pill` only for chips and tags. Nothing else.
- Elevation is declared once per element: a border **or** a shadow, not both. Cards on dark grounds use a `line` border. Floating things (popovers, floor labels, toasts) use `shadow-float`.
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
::selection { background: color-mix(in oklab, var(--color-brand) 55%, transparent); color: #fff; }
html { color-scheme: dark; caret-color: var(--color-brand-hi); scrollbar-color: var(--color-line-strong) transparent; accent-color: var(--color-brand); }
a { text-underline-offset: 0.2em; text-decoration-thickness: 1px; }
```
