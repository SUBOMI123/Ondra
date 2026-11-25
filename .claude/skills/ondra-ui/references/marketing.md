# Marketing (Persuade mode)

Applies to `apps/site` and any marketing asset. Copy comes from `docs/marketing/positioning.md`; change positioning there first.

## The concept

The site is a visit to the dealership after hours (brand: Night Shift, see `tokens.md`):
1. **Hero:** the first frame of the 3D walk under a night scrim, the headline "Your dealership, fully staffed." and Book a demo.
2. **Walk in:** the floor tour (`components/FloorTour.tsx`), a Blender render of one continuous camera path played back as you scroll. Frost-glass agents sit at every desk with a label pinned to each (role, desk, what it is doing right now).
3. **The owner's office:** empty, with a red light on the desk phone. The only red label, because VIPs never reach the AI.
4. **Close:** "None of them are people. All of them are on your side."
Then the product (the inbox, with the AI's work in Ondra blue), and the details for a dealer who is now interested.

The signature moves are the 3D floor and working product UI. Everything around them stays quiet: dark bands, Funnel type, generous space, one blue signal, no ambient animation competing with them.

## 3D art direction

Source and rules are in `design/3d/README.md`. In short: polished concrete, walnut slat walls, amber-lit pendants, a glass wall onto the night city; agents are faceless frosted-glass human forms with a faint blue rim (not robots, not people); cars carry no badges, plates or logos and must be licensed for commercial use before the frames ship (see `docs/DECISIONS.md`). Frames ship compressed (WebP or JPEG around 60-80KB each), never the raw renders.

## Rules

- **The primary action is visible in the first viewport** at every width (Book a demo). The walk-through comes straight after the hero, and the hero must work without it.
- **Hero:** the first frame of the walk full-bleed, darkened toward the text side with a night scrim so the headline reads at 7:1 or better. Headline in `font-display text-display`, no accent word or colour. No eyebrow chip. No screenshot or chat card competing with the headline.
- **Imagery:** rendered frames of the 3D floor, or real photography of the pilot dealer (with written permission). No generated stock photos, no badges, plates or faces. Self-host every image, serve smaller versions to phones, set width and height, `fetchPriority="high"` only on the hero.
- **The floor tour** is scrubbed by scroll, never timed: scroll position picks the frame of the rendered walk, neighbouring frames blend, and phones get the portrait render. Labels are pinned per frame from `anchors.json`, fade at the screen edges and never sit under the sticky nav. Reduced motion or no JS: still frames with labels listed. A thin Ondra-blue progress line shows position on the floor.
- **Show the product.** At least one faithful product artefact built in HTML with the dashboard's tokens (the inbox), marked "Example conversation". It must obey `ai-and-vip.md`.
- **Sticky nav** appears once the hero leaves the viewport, with Book a demo always one tap away.
- **Sections are not a card kit.** Vary structure: a full-bleed band, a two-column with a real artefact (a WhatsApp briefing, a VIP call card), a list with rules, a form. Never three identical icon cards in a row as the page's backbone.
- **No eyebrows.** A section heading is enough. If a section genuinely needs a label (a step in a real sequence), make it part of the content.
- **Alternate grounds with intent:** `bg` for explanation, `night` for the two or three moments that matter (hero, WhatsApp-first, getting started), `bg-2` for the demo form. Separate bands with a `line` hairline so dark sections don't run together.
- **Motion budget:** the walk-through is the authored moment. Elsewhere at most one restrained reveal per section on scroll (opacity and 8-12px of travel, 400-500ms, `ease-out-expo`), content visible without JS, nothing looping. The hero photo may settle once on load (scale 1.04 to 1, 1.2s) and never again.
- **Proof:** only real proof. Until the pilot produces numbers, describe the pilot honestly ("We're building Ondra with an independent luxury dealer in Dallas who exports to Nigeria"). No logo walls, no counters, no testimonials without written permission.
- **Forms:** short, labelled above the field, a 52px submit button, inline errors, a honeypot instead of a captcha. Say what happens next.
- **Phones first:** dealers open the link from WhatsApp on a phone. Check 390px before 1440px.

## Copy

Dealer words: calls, WhatsApp, buyers, the lot, test drives, video walkarounds, service bays, deposits, exporters. Short declarative sentences. Concrete times and places (2:14 am in Dallas, a buyer in Lagos). Headlines state a fact about the dealer's day, not a feature.
