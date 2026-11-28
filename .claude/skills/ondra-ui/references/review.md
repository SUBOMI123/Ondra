# Review before calling UI work done

Screenshot at 390, 768 and 1440 wide (Playwright is preinstalled: `require('playwright')`, `deviceScaleFactor: 1` for your own checks). Answer each item with a selector, a computed value or "n/a", never "looks fine".

## 1. Product rules (P0 if any fail)

- [ ] VIP surfaces contain no Ondra-blue element: `[data-vip] [data-slot^="ai-"]` matches nothing.
- [ ] Every AI-authored item is labelled in words, not only coloured.
- [ ] Red appears only on overdue elements. VIPs use the ink tag and ring, never a crown or red.
- [ ] No sample content has the AI committing to a price, discount or delivery date.
- [ ] Opted-out contacts cannot be messaged from this screen.

## 2. Tokens and slop tells

- [ ] No hex literals in components (`grep -nE "#[0-9a-fA-F]{3,8}" components app` outside token files).
- [ ] No tracked uppercase eyebrow above a heading; no middle-dot metadata strings; no 01/02 markers on non-sequences.
- [ ] No gradient text, coloured glow, radial halo, decorative glass, nested cards, side bar on a rounded card.
- [ ] Radii are only control, card, panel or pill. Each element has a border or a shadow, not both.
- [ ] Display width (`font-display`) only on titles, headings and large numerals.
- [ ] Copy passes `copy.md` (no buzzwords, buttons say what happens).

## 3. Accessibility and contrast

- [ ] Body text 4.5:1, large text and icons and focus rings 3:1. Known traps: the blue fill colour as small text on dark (use `brand-text`), dark text on blue fills (use white), `muted-foreground` on `muted` surfaces.
- [ ] Visible focus on every interactive element, keyboard order matches visual order, Escape closes overlays.
- [ ] Touch targets 44px (24px absolute minimum).
- [ ] Images have alt text or `alt=""` when decorative; icon-only buttons have `aria-label`.
- [ ] Reduced motion: loops stop, travel goes, state feedback stays. The walk-through is skipped.
- [ ] Headings in order, one `h1`, landmarks present.

## 4. Layout and states

- [ ] No horizontal scroll at 390px (`document.documentElement.scrollWidth === innerWidth`).
- [ ] Text never clipped; long names and numbers wrap or truncate with a title.
- [ ] Prose under 72ch; space above headings exceeds space below.
- [ ] Every state exists: loading skeleton at final size, empty that teaches, error with recovery, disabled.
- [ ] Content visible at rest without JS or scrolling (no element left at `opacity: 0` waiting for an observer).

## 5. Cognitive load (4+ failures is critical)

Single focus per view; chunks of four or fewer; related things grouped; clear hierarchy; one decision at a time; four or fewer visible options; no need to remember something from another screen; detail disclosed progressively. One primary action, one or two secondary, the rest in a menu.

## Severity

P0 broken task, data loss or a product-rule violation. P1 major usability or WCAG AA failure. P2 minor. P3 polish (keep these few). Fix P0 and P1 before shipping.
