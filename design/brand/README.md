# Ondra logo

The wordmark is Inter 500 outlines with a speedometer for the o. The dial is the letter colour and the needle is the AI blue.

| File | Use |
|---|---|
| `ondra-logo-on-dark.svg` | Dark backgrounds (cream letters, `#8AA6FF` needle) |
| `ondra-logo-on-light.svg` | Light or champagne backgrounds (`#1B140B` letters, `#3F5BD6` needle) |
| `ondra-logo-mono.svg` | One colour (`currentColor`): stamps, embroidery, single-ink print |
| `ondra-icon.svg`, `ondra-icon-on-champagne.svg` | App icon, avatar |
| `apps/site/public/favicon.svg` | Favicon (thicker dial so it holds at 16 px) |

The site uses `apps/site/components/Wordmark.tsx`, which takes the text colour. Keep the logo at least 18 px tall, and leave clear space around it at least the width of the o.
