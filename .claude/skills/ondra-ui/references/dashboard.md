# Dashboard (Operate mode)

Applies to `apps/web`. The reference screens are in `design/mockups/app.html` (Today, Inbox, Calls, Calendar, Clients, Tasks, Settings).

## Principles

- The tool disappears into the task. Scanability, consistency and the real usage scene (a salesperson on the floor with a tablet, the owner on a phone at 7am) outrank expression.
- The brand lends four things only: type, palette, density, and one signature move. It never supplies the layout, navigation model or controls; those follow established patterns (sidebar plus top bar, tables, sheets).
- **Signature move: the AI-blue provenance trail.** Everything Ondra did is visibly blue and labelled, everything people did is not. A dealer can scan any screen and see what the AI handled. See `ai-and-vip.md`.
- A grey screen with one accent is not restraint; it is the category default without the polish. Get the details right: tabular numerals, aligned baselines, real states, themed scrollbars and selection.

## Layout and density

- Ink sidebar (the mockup's dark rail), Paper canvas, white cards with a border (no shadow).
- Fixed type scale: 12, 14, 16, 20, 24, 30px. `font-display` (wdth 125) only for page titles and KPI values.
- Dense lists at 36px rows, default 44px. Touch targets 44px on tablet breakpoints.
- Group by proximity before adding containers. Never nest cards.
- Detail opens in a Sheet or a resizable side pane, not a modal. Modals only for short blocking decisions.
- Selected list row: square row, 3px amber bar on the left edge (allowed because the row is square), `accent` background.

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

Map: phone `IconPhone` (Incoming/Outgoing/X for direction and missed), WhatsApp `IconBrandWhatsapp`, text `IconMessage`, email `IconMail`, Instagram `IconBrandInstagram`, AI `IconSparkles` (always with AI blue and the word "Ondra"), VIP `IconCrownFilled` (VIP red; not a star, which reads as favourite), overdue `IconClockExclamation`. Never `IconRobot`. Icons take `currentColor`; decorative ones get `aria-hidden`; icon-only buttons get `aria-label`.

## Charts

shadcn Chart on Recharts 3 (`recharts@^3.11`; React 19 compatible). Not Tremor: Tremor Raw is still on React 18 and Recharts 2 and has no empty or error states. Borrow Tremor's ideas only: one `valueFormatter` per chart for axis and tooltip, BarList and CategoryBar (plain divs).

Colour carries one meaning only, who handled the work:
| Series | Token | Notes |
|---|---|---|
| Ondra | `--chart-ai` `#5B8DEF` | AI labels and text use `#1E3F7A` |
| Staff | `--chart-staff` `#F2A33A` fill with `#C27A12` edge | Amber fill alone fails 3:1 on white |
| Owner ("you") | `--chart-ink` `#16171B` | |
| Other / last period | `--chart-muted` `#8A8D95`, dashed for comparisons | Drawn behind |
Every other breakdown (channels, stages, makes) is one ink hue on `--chart-track` `#ECEAE5`; identity comes from icons and labels. VIP red is never a series. Bad deltas are muted with a down arrow, never red. At most 4 series; group the rest as Other. No donuts; use a stacked CategoryBar.

Marks: bars start at 0, 4px top radius, `maxBarSize={32}`; lines 2px monotone, no dots, `activeDot r=4`; area fill at 15%, no gradient; horizontal gridlines only; axis text 12px muted, tabular, 3-5 ticks. Keep `accessibilityLayer` on, add an `aria-label` summary sentence and a visually hidden table. `isAnimationActive="auto"`, 300ms, off on refresh. Parent must have a fixed height (a 0-height parent renders nothing; charts in hidden tabs mount at 0 width). Live data is shown as counts and badges, not charts.

Wrap every chart and KPI in a `ChartCard` that handles loading (skeleton at final size), empty (icon, one sentence, one action; never empty axes), zero (render 0), too few points (list instead of a line), error (message, Try again, request id) and stale ("Updated 12 min ago").

## KPI tiles

One hero tile (Ink background, 2fr) plus three standard tiles; two columns under 1000px. Anatomy: plain-words label (13px muted), value (`font-display`, 600, 34px or 44px for the hero, tabular), one context line, optional delta chip (`▲ 12% vs last week`, ok-green when good, muted when flat or bad; "good" direction is per metric) and optional 32px sparkline (ink, 1.5px, at least 7 points). Attribute in words: "19 by Ondra, 4 by staff", with "by Ondra" in AI blue.

## Formatting

One module, `apps/web/lib/format.ts`, unit-tested, with cached `Intl` formatters using the **tenant's** locale and time zone and the deal's currency (never the browser default). Compact money for KPIs and axes ("$1.42M"), whole dollars for detail (no cents on car prices), signed percentages, durations ("41s", "3m 05s"), and the dual clock for overseas buyers ("2:14 am Dallas, 9:14 am Lagos"). Amounts arrive as integer minor units. Never sum mixed currencies in the UI; show "≈" when the API converted. Null or zero durations render as an em dash.

## Component documentation

No Storybook yet. Add it when `apps/web` has about ten shared components: `@storybook/nextjs-vite` with the a11y addon (`test: "error"`) and the vitest addon, importing `globals.css` in the preview. That is new infrastructure, so ask first.
