# apps/site: Ondra marketing site

A single landing page, built as a static export with Next.js, TypeScript, Tailwind v4 and three.js. It's separate from `apps/web` (the dashboard) so it can ship and change on its own.

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # static files in out/
```

Deploy `out/` anywhere static: Vercel, Netlify, Cloudflare Pages or S3.

## Configuration

Copy `.env.example` to `.env.local`.

- `NEXT_PUBLIC_DEMO_FORM_ENDPOINT`: where the demo form POSTs JSON. Until it's set, the form opens the visitor's email client addressed to `NEXT_PUBLIC_CONTACT_EMAIL`. Formspree or similar is enough for now; point it at `apps/api` later.
- `NEXT_PUBLIC_CONTACT_EMAIL`, `NEXT_PUBLIC_SITE_URL`: placeholders until the name and domain are confirmed.

## Assets

- `public/exterior.jpg` (optional): hero background. Use the pilot dealer's showroom, with permission. Without it, the hero uses a gradient.
- TODO: Open Graph image (`app/opengraph-image.png`, 1200×630).

## Notes

- The copy comes from `docs/marketing/positioning.md`, which also lists claims we can't make yet.
- The 3D walk-through (`components/Walkthrough.tsx`) loads three.js only when a visitor nears that section. It's skipped for visitors with reduced motion or no WebGL; the agents grid carries the same content.
