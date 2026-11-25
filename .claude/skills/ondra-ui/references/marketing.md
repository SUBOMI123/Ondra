# Marketing (Persuade mode)

Applies to `apps/site` and any marketing asset. Copy comes from `docs/marketing/positioning.md`; change positioning there first.

## The concept

The site is a visit to the dealership after hours:
1. **Outside:** the showroom at dusk through glass, warm sodium light, the headline "Your dealership, fully staffed."
2. **Walk in:** the three.js floor, scroll-driven, every desk staffed by a faceless mannequin with a label (role, desk, what it is doing right now).
3. **The owner's office:** the only red label, because VIPs never reach the AI.
4. **Close:** "None of them are people. All of them are on your side."
Everything after that explains the details for a dealer who is now interested.

The signature moves are the dusk showroom photograph and the walk-through. Everything around them stays quiet: plain Paper sections, Archivo, generous space, no ambient animation competing with them.

## Rules

- **The primary action is visible in the first viewport** at every width (Book a demo). The walk-through comes straight after the hero, and the hero must work without it.
- **Hero:** the showroom photograph full-bleed, darkened toward the text side with an Ink gradient so the headline reads at 7:1 or better. The photo should be felt, not read. Headline in `font-display text-display`, roman, no accent word. No eyebrow chip. No screenshot or chat card competing with the headline.
- **Imagery:** real or generated photography of dealership interiors and cars at night, warm light. No badges, logos, licence plates or people's faces. Replace with the pilot dealer's showroom once we have written permission. Self-host every image (`public/`), serve a 960w version to phones, set width and height to avoid layout shift, `fetchPriority="high"` only on the hero.
- **The walk-through** is scrubbed by scroll, never timed. It is code-split and loaded near the viewport. Under reduced motion or without WebGL it renders nothing and the agents section carries the content. Labels stay inside the viewport on phones; on narrow screens they drop the "doing" line. The figures are faceless architectural mannequins: realistic people would contradict "None of them are people" and cost megabytes per figure.
- **Sections are not a card kit.** Vary structure: a full-bleed band, a two-column with a real artefact (a WhatsApp briefing, a VIP call card), a list with rules, a form. Never three identical icon cards in a row as the page's backbone.
- **No eyebrows.** A section heading is enough. If a section genuinely needs a label (a step in a real sequence), make it part of the content.
- **Alternate grounds with intent:** Paper for explanation, Ink for the two or three moments that matter (WhatsApp-first, getting started), Paper-2 for the demo form. Not every other section.
- **Motion budget:** the walk-through is the authored moment. Elsewhere at most one restrained reveal per section on scroll (opacity and 8-12px of travel, 400-500ms, `ease-out-expo`), content visible without JS, nothing looping. The hero photo may settle once on load (scale 1.04 to 1, 1.2s) and never again.
- **Proof:** only real proof. Until the pilot produces numbers, describe the pilot honestly ("We're building Ondra with an independent luxury dealer in Dallas who exports to Nigeria"). No logo walls, no counters, no testimonials without written permission.
- **Forms:** short, labelled above the field, a 52px submit button, inline errors, a honeypot instead of a captcha. Say what happens next.
- **Phones first:** dealers open the link from WhatsApp on a phone. Check 390px before 1440px.

## Copy

Dealer words: calls, WhatsApp, buyers, the lot, test drives, video walkarounds, service bays, deposits, exporters. Short declarative sentences. Concrete times and places (2:14 am in Dallas, a buyer in Lagos). Headlines state a fact about the dealer's day, not a feature.
