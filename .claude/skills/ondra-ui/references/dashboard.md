# Dashboard (Operate mode)

Applies to `apps/web`, which is built on shadcn/ui's `dashboard-01` block and new-york-v4 components with shadcn's neutral theme (see `docs/DECISIONS.md`, 2026-11-25). Use shadcn components as they are and change tokens, not component internals. `design/prototypes/system.html` is an earlier custom direction, kept for reference only; where it conflicts with `apps/web/app/globals.css`, the app wins. `design/mockups/app.html` is older: keep its screen list and content ideas, but take colour, type and layout from the prototype.

## Principles

- The tool disappears into the task. Scanability, consistency and the real usage scene outrank expression: a salesperson on the floor with a phone, the owner at 7am.
- The brand lends type, palette and one signature move. It never supplies the layout, navigation model or controls; those follow established patterns (sidebar plus top bar, tables, sheets).
- **Signature move: the who-did-it column.** Every thread event has an actor gutter: the customer by name, **Ondra** in AI blue with the sparkles icon, or a person's initials. Everything Ondra did is blue and labelled, and nothing else is blue. See `ai-and-vip.md`.

## Lessons from the first screens (apply to every page)

- **Lead with what needs a person.** Ondra handles most work end to end, so a list's default view is "Needs you", each row saying why in plain words ("VIP called. Waiting 2 h", "Draft to approve"). What Ondra handled sits one tab away. Never present a booked test drive and a waiting VIP as equals.
- **One signal per meaning.** A crown means VIP; don't add a red avatar, a red pill and red text to the same row. Red is the waiting time or the overdue date, nothing else.
- **Text before pills.** A list where every row has a coloured badge has no hierarchy. Prefer a short line of plain text; keep pills for the one status that must stand out.
- **The work gets the room.** On work screens (Inbox), collapse the app sidebar to icons and keep secondary detail (contact, consent) behind a disclosure.
- **One primary action per item.** A draft has "Approve and send" plus a quiet "Edit". A call has one "Play". Everything else goes in a menu.
- **Remove template leftovers.** Drag handles, checkboxes and actions with no real job (no bulk actions, no manual order) are noise.
- **Same thing in the same place.** Repeated cards and rows keep one layout: if one card shows the owner at the bottom, every card does; optional details get their own line rather than borrowing another field's slot.
- **No dead ends.** Don't render a link or button for something that doesn't exist yet; leave it out until it works.
- **Red marks the item, not the paragraph.** On an overdue row, the title or date is red; the explanation stays muted.
- **Screen-reader-only text needs a positioned parent** (`relative` on the card or row). Otherwise it is placed against the page and, inside a scrolling board, widens the whole page.
- **Pick the pattern for the job.** A personal to-do list is a list grouped by urgency with a checkbox, not a status board; a pipeline is a board.
- **Run the gate:** `npm run review:ui` in `apps/web` (every page, 4 widths, both themes, product-rule and source checks) plus a screenshot read against `review.md` section 5 before calling a page done.

## Themes

Light, dark and "Device" (follows the OS, the default). The user picks in their menu and the choice is saved per user. Tokens are defined once on `:root` (light). Dark redefines them under `[data-theme="dark"]` and under `prefers-color-scheme: dark` when no theme is set. Components only ever use tokens.

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` / `surface` / `surface-2` / `hover` | `#F4F3F0` / `#FFFFFF` / `#FAF9F6` / `#F1EFEA` | `#0D0B09` / `#15120E` / `#1A1612` / `#1F1A15` | Canvas, cards and panels, selected row, hover |
| `line` / `line-strong` | `#E5E2DC` / `#D2CDC4` | warm white 9% / 17% | Hairlines, input borders |
| `fg` / `fg-2` / `muted` | `#191510` / `#4A443B` / `#776F63` | `#F6EFE3` / `#D9CFBF` / `#A99D8B` | Text levels |
| `action` / `on-action` | `#1B140B` / `#F6EFE3` (espresso pill) | `#EAD9B5` / `#1B140B` (champagne pill) | Primary buttons only |
| `select` / `on-select` | `#EFE3C8` / `#1B140B` | `#EAD9B5` / `#1B140B` | Pressed chips, segmented controls |
| `ai` / `ai-subtle` / `ai-line` | `#3F5BD6` / `#EEF1FC` / `#CBD4F6` | `#B3C5FF` / `#161A2C` / `#2B3563` | Anything Ondra did. Never an action, never focus |
| `vip` / `vip-subtle` | `#C93C3C` / `#FBEDEC` | `#FF7B7B` / `#2E1416` | VIP and overdue only |
| `ok`, `warn` (+ `-subtle`) | `#1E7F4F`, `#A3600E` | `#4ADE9A`, `#F2A33A` | Status: showed up, due soon, on hold |
| `focus` | `#1B140B` | `#EAD9B5` | 2px focus ring, 2px offset |
| `sidebar` | `#12100C` | `#090706` | The sidebar is dark in both themes |

## Layout and density

- Sidebar (232px) plus a 56px top bar with search (⌘K) on desktop. Under 860px: no sidebar, five bottom tabs (Today, Inbox, Calendar, Tasks, More), with the VIP count as a badge on Inbox.
- Inbox: list (340px), thread, and a brief panel (300px) that hides under 1180px.
- Type: Inter only, sizes 12, 13, 14, 16, 20, 24, 30px. Headings weight 500 (page titles 600 at 16px in the top bar); body 400. Tabular numerals only where digits line up (times, prices, counts), never globally, because Inter's tabular setting also spaces out hyphens. JetBrains Mono only for VINs and stock numbers.
- Radius: controls 10px, buttons and chips fully round, cards and panels 14 to 16px, list rows square. Never nest cards.
- Rows default 44px; dense lists 36px. Touch targets 44px under 860px.
- Detail opens in a Sheet or a side pane, not a modal. Modals only for short blocking decisions.
- Selected list row: square row, a 3px `fg` bar on the left edge, `surface-2` background. Not blue: blue means Ondra.

## States (every component ships all of them)

Default, hover, focus-visible, active, disabled, loading, empty, error. Plus, where relevant: AI drafting, AI draft awaiting approval, sent by AI, edited by a person, VIP, opted out.
- Loading: a skeleton at the exact final size. No spinners inside content.
- Empty states teach: say what will appear here and how it gets there, with one action. Distinguish first use, no results, filtered out, no permission and failure.
- Errors: what failed, why if known, how to recover, plus the request id in muted text. No apology, no error codes as the headline.

## Icons

Tabler only (`@tabler/icons-react`), imported through one file, `apps/web/lib/icons.ts`, for domain concepts.

| Size | Where | Stroke |
|---|---|---|
| 16 | Inline with 13-14px text, table cells, tags, small buttons | 1.75 |
| 20 | Sidebar, default buttons, list-row channel glyphs | 1.5 |
| 24 | Page headers; empty states use 40 at stroke 1.25 | 1.5 |

Map: phone `IconPhone` (Incoming/Outgoing/X for direction and missed), WhatsApp `IconBrandWhatsapp`, text `IconMessage`, email `IconMail`, Instagram `IconBrandInstagram`, AI `IconSparkles` (always with Ondra blue and the word "Ondra"), VIP `IconCrownFilled` (`vip` colour; not a star, which reads as favourite), overdue `IconClockExclamation`. Never `IconRobot`. Icons take `currentColor`; decorative ones get `aria-hidden`; icon-only buttons get `aria-label`.

## Charts

shadcn Chart on Recharts 3 (`recharts@^3.11`; React 19 compatible). Not Tremor: Tremor Raw is still on React 18 and Recharts 2 and has no empty or error states. Borrow Tremor's ideas only: one `valueFormatter` per chart for axis and tooltip, BarList and CategoryBar (plain divs).

Colour carries one meaning only, who handled the work:
| Series | Token | Notes |
|---|---|---|
| Ondra | `--chart-ai` = `ai` token (`#3F5BD6` light, `#B3C5FF` dark) | AI labels and text use the same token |
| Staff | `--chart-staff` = `muted` token | Neutral: people are not a brand colour |
| Owner ("you") | `--chart-ink` = `fg` token | |
| Other / last period | `--chart-muted` = `line-strong`, dashed for comparisons | Drawn behind |
Every other breakdown (channels, stages, makes) is one night hue on `--chart-track` = `hover` token; identity comes from icons and labels. VIP red is never a series. Bad deltas are muted with a down arrow, never red. At most 4 series; group the rest as Other. No donuts; use a stacked CategoryBar.

Marks: bars start at 0, 4px top radius, `maxBarSize={32}`; lines 2px monotone, no dots, `activeDot r=4`; area fill at 15%, no gradient; horizontal gridlines only; axis text 12px muted, tabular, 3-5 ticks. Keep `accessibilityLayer` on, add an `aria-label` summary sentence and a visually hidden table. `isAnimationActive="auto"`, 300ms, off on refresh. Parent must have a fixed height (a 0-height parent renders nothing; charts in hidden tabs mount at 0 width). Live data is shown as counts and badges, not charts.

Wrap every chart and KPI in a `ChartCard` that handles loading (skeleton at final size), empty (icon, one sentence, one action; never empty axes), zero (render 0), too few points (list instead of a line), error (message, Try again, request id) and stale ("Updated 12 min ago").

## KPI tiles

One hero tile (2fr) plus three standard tiles; two columns under 1000px. Anatomy: plain-words label (13px muted), value (Inter 600, 34px or 44px for the hero, tabular), one context line, optional delta chip (`▲ 12% vs last week`, ok-green when good, muted when flat or bad; "good" direction is per metric) and optional 32px sparkline (ink, 1.5px, at least 7 points). Attribute in words: "19 by Ondra, 4 by staff", with "by Ondra" in Ondra blue.

## Formatting

One module, `apps/web/lib/format.ts`, unit-tested, with cached `Intl` formatters using the **tenant's** locale and time zone and the deal's currency (never the browser default). Compact money for KPIs and axes ("$1.42M"), whole dollars for detail (no cents on car prices), signed percentages, durations ("41s", "3m 05s"), and the dual clock for overseas buyers ("2:14 am Dallas, 9:14 am Lagos"). Amounts arrive as integer minor units. Never sum mixed currencies in the UI; show "≈" when the API converted. Null or zero durations render as an em dash.

## Component documentation

No Storybook yet. Add it when `apps/web` has about ten shared components: `@storybook/nextjs-vite` with the a11y addon (`test: "error"`) and the vitest addon, importing `globals.css` in the preview. That is new infrastructure, so ask first.
