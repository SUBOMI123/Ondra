# Image prompts

The marketing photography in `apps/site/public/` was generated with Figma's image generator (model `gpt-image-2.5-flare`, 2048x1152 requested, 1536x864 delivered) in the Figma file "Ondra – marketing imagery". Art direction rules are in `.claude/skills/ondra-ui/references/marketing.md`. Keep the shared phrases word for word so new scenes match; change only the scene sentence.

These are placeholders. A real night shoot of the pilot dealer's showroom (with written permission) should replace them, following the same art direction.

## Shared phrases

- **Architecture:** polished pale grey concrete floor with soft reflections, warm walnut vertical slat wall panels, black cylindrical pendant lamps glowing warm sodium-amber, floor-to-ceiling glass with a dark blue night sky outside.
- **Robots:** elegant humanoid service robot, refined industrial design, matte warm-white ceramic shell, graphite grey joints, slim realistic proportions, smooth featureless dark glass face visor with a thin warm amber light line, no eyes, no mouth.
- **Camera:** eye-level camera, 35mm full-frame lens, cinematic low-key lighting, rich blacks, natural reflections, subtle film grain.
- **Always end with:** No readable text, no logos, no brand badges, no license plates, no humans.

## Scenes

| File | Scene sentence |
|---|---|
| `hero-showroom.jpg` | Wide cinematic photograph of a modern luxury car dealership showroom at dusk, seen from outside through tall floor-to-ceiling glass. Three dark luxury SUVs and a silver sports coupe on a polished concrete floor. Cars on the right two-thirds, darker negative space on the left for headline text. |
| `floor/entrance.jpg` | The moment of walking in through the open glass front doors: a long central aisle, unbadged cars on both sides (black SUV left, silver grand tourer and bronze sedan right), rows of walnut desks with robots further down, a glass-walled office with a warm desk lamp at the far end. Symmetrical composition. |
| `floor/desks-1.jpg` | Left foreground: a robot at a walnut desk wearing a slim black headset, mid phone call. Right: a second robot at two monitors showing softly blurred chat bubbles. Behind them a black SUV and a silver grand tourer. |
| `floor/desks-2.jpg` | Left: a robot at a monitor showing a blurred weekly calendar with amber blocks, car keys on a small tray. Right: a second robot with a monitor of blurred service schedule bars; behind it, through interior glass, a bright service workshop with a car on a lift. |
| `floor/desks-3.jpg` | Left: a robot standing beside its desk holding a slim tablet, turning as if passing work on. Right: a second robot at a desk with blurred message drafts on screen, envelopes and a coffee cup. A bronze sedan on display behind. |
| `floor/office.jpg` | A private glass-walled owner's office seen from just outside the door: walnut executive desk, empty black leather chair, brass desk lamp, closed laptop, a desk phone with a single small red light. No robots and no people inside. |

Process each image into `name.jpg` (JPEG q80, progressive) and `name-960.jpg` (960x540, q76). Check every scene at full size for artefacts (hands, chair legs, warped wheels, text) before using it, and regenerate rather than retouch.
