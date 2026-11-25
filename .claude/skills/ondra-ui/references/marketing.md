# Marketing (Persuade mode)

Applies to `apps/site` and any marketing asset. Copy comes from `docs/marketing/positioning.md`; change positioning there first.

## The concept

The site is a visit to the dealership after hours:
1. **Outside:** the showroom at dusk through glass, warm sodium light, the headline "Your dealership, fully staffed."
2. **Walk in:** the floor tour (`components/FloorTour.tsx`): five photographs on a sticky stage, scroll-driven. Each desk is staffed by a robot agent with a label pinned over it (role, desk, what it is doing right now).
3. **The owner's office:** empty, with a red light on the desk phone. The only red label, because VIPs never reach the AI.
4. **Close:** "None of them are people. All of them are on your side."
Then the product (the inbox, with the AI's work in blue), and the details for a dealer who is now interested.

The signature moves are the photography and the tour. Everything around them stays quiet: plain Paper sections, Archivo, generous space, no ambient animation competing with them.

## Photography art direction

All imagery shares one world, so scenes cut together:
- **Architecture:** polished pale concrete floor with reflections, walnut vertical slat walls, black cylindrical pendants glowing sodium amber, floor-to-ceiling glass, night outside.
- **Agents:** humanoid robots in matte warm-white ceramic with graphite joints, slim realistic proportions, a smooth dark glass visor with one thin amber light line. No eyes, no mouth, no chrome, no glowing red, nothing menacing. They work: headsets, keyboards, tablets.
- **Cars:** real-looking luxury cars, unbadged. No logos, plates or readable text anywhere.
- **No humans.** The owner's office is empty; the owner is the visitor.
- **Camera:** eye level, 35mm, low-key cinematic light, rich blacks, subtle grain. 16:9 at 1536x864 or larger.
- Generated today with Figma's image generator (prompts in `docs/marketing/image-prompts.md`); replace with a real shoot of the pilot dealer's showroom when permitted. Save each as `name.jpg` (q80) plus `name-960.jpg` for phones.

## Rules

- **The primary action is visible in the first viewport** at every width (Book a demo). The walk-through comes straight after the hero, and the hero must work without it.
- **Hero:** the showroom photograph full-bleed, darkened toward the text side with an Ink gradient so the headline reads at 7:1 or better. The photo should be felt, not read. Headline in `font-display text-display`, roman, no accent word. No eyebrow chip. No screenshot or chat card competing with the headline.
- **Imagery:** real or generated photography of dealership interiors and cars at night, warm light. No badges, logos, licence plates or people's faces. Replace with the pilot dealer's showroom once we have written permission. Self-host every image (`public/`), serve a 960w version to phones, set width and height to avoid layout shift, `fetchPriority="high"` only on the hero.
- **The floor tour** is scrubbed by scroll, never timed. Desktop: each scene dollies in slowly (scale 1 to 1.1 about a focus point) and the next crossfades over it. Phones: the camera pans from one desk to the other (hold, move, hold) so neither is cropped away. Labels are pinned to image coordinates and follow zoom and pan; they fade at the screen edges and never sit under the sticky nav. Reduced motion or no JS: the same scenes as a static sequence with labels listed under each photo. A thin amber progress line shows position on the floor.
- **Show the product.** At least one faithful product artefact built in HTML with the dashboard's tokens (the inbox), marked "Example conversation". It must obey `ai-and-vip.md`.
- **Sticky nav** appears once the hero leaves the viewport, with Book a demo always one tap away.
- **Sections are not a card kit.** Vary structure: a full-bleed band, a two-column with a real artefact (a WhatsApp briefing, a VIP call card), a list with rules, a form. Never three identical icon cards in a row as the page's backbone.
- **No eyebrows.** A section heading is enough. If a section genuinely needs a label (a step in a real sequence), make it part of the content.
- **Alternate grounds with intent:** Paper for explanation, Ink for the two or three moments that matter (WhatsApp-first, getting started), Paper-2 for the demo form. Not every other section.
- **Motion budget:** the walk-through is the authored moment. Elsewhere at most one restrained reveal per section on scroll (opacity and 8-12px of travel, 400-500ms, `ease-out-expo`), content visible without JS, nothing looping. The hero photo may settle once on load (scale 1.04 to 1, 1.2s) and never again.
- **Proof:** only real proof. Until the pilot produces numbers, describe the pilot honestly ("We're building Ondra with an independent luxury dealer in Dallas who exports to Nigeria"). No logo walls, no counters, no testimonials without written permission.
- **Forms:** short, labelled above the field, a 52px submit button, inline errors, a honeypot instead of a captcha. Say what happens next.
- **Phones first:** dealers open the link from WhatsApp on a phone. Check 390px before 1440px.

## Copy

Dealer words: calls, WhatsApp, buyers, the lot, test drives, video walkarounds, service bays, deposits, exporters. Short declarative sentences. Concrete times and places (2:14 am in Dallas, a buyer in Lagos). Headlines state a fact about the dealer's day, not a feature.
