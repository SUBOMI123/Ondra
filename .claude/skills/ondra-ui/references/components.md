# Components

The component base is **shadcn/ui on Radix**, styled with Ondra tokens. Components are copied into the repo and owned by us, so restyle them freely, but keep their structure and accessibility.

## Setup decisions (record in `docs/DECISIONS.md` when `apps/web` starts)

- **Base: Radix, not Base UI.** Since July 2026 `npx shadcn init` defaults to Base UI. Run `npx shadcn@latest init -b radix`. Reasons: cmdk and vaul sit on Radix Dialog, Radix is mature, and shadcn has committed to ship every component for both bases. Base UI is the rejected alternative; revisit if vaul becomes a problem (Base UI ships its own Drawer).
- **Unified `radix-ui` package**, not individual `@radix-ui/react-*` packages: `import { Dialog as DialogPrimitive } from "radix-ui"`.
- **Icons: Tabler.** Set `"iconLibrary": "tabler"` in `components.json` *before* adding components, so generated code imports `@tabler/icons-react`. Lucide has no WhatsApp or Instagram marks.
- **`cn`:** `export { cn } from "cn"` once the `cn` package is at least two weeks old on npm; otherwise `twMerge(clsx(...))` with `tailwind-merge@3`. Same behaviour.
- **Animations:** `tw-animate-css` plus `@import "shadcn/tailwind.css"` (gives `data-open:` / `data-closed:` variants).
- **Monorepo (`packages/ui` shared by site and web)** is new infrastructure. Ask before creating it.

## Theme mapping

shadcn reads raw variables on `:root`, mapped to utilities with `@theme inline`. Ondra values:

```css
:root {
  --radius: 0.75rem;
  --background: #F1EFEA;  --foreground: #16171B;
  --card: #FFFFFF;        --card-foreground: #16171B;
  --popover: #FFFFFF;     --popover-foreground: #16171B;
  --primary: #F2A33A;     --primary-foreground: #1A1206;   /* ink text on amber, never white */
  --secondary: #ECEAE5;   --secondary-foreground: #16171B;
  --muted: #ECEAE5;       --muted-foreground: #5F626A;
  --accent: #FFF3E0;      --accent-foreground: #7A4A08;    /* hover/selected rows */
  --destructive: #16171B; --destructive-foreground: #FFFFFF; /* Ink, not red: red is VIP-only */
  --border: #E2E0DA;  --input: #DDD9D1;  --ring: #16171B;
  --ai: #1E3F7A;  --ai-subtle: #EAF1FF;  --ai-border: #C9DAF8;  --ai-mark: #5B8DEF;
  --vip: #A3191E; --vip-subtle: #FFE9EA;
  --success: #1F6B45; --success-subtle: #E6F4EC;
  --sodium-text: #7A4A08;  /* the only amber allowed as text on light surfaces */
  --sidebar: #17181C; --sidebar-foreground: #E4E5EA;
  --sidebar-primary: #F2A33A; --sidebar-primary-foreground: #1A1206;
  --sidebar-accent: #24262C; --sidebar-accent-foreground: #FFFFFF;
  --sidebar-border: #2A2C33; --sidebar-ring: #F2A33A;   /* amber ring is fine on Ink */
}
@theme inline {
  --color-background: var(--background); --color-foreground: var(--foreground);
  /* …every pair above as --color-<name>: var(--<name>) … */
  --color-ai: var(--ai); --color-ai-subtle: var(--ai-subtle); --color-ai-border: var(--ai-border);
  --color-vip: var(--vip); --color-vip-subtle: var(--vip-subtle);
}
```
Two deliberate departures from shadcn defaults: `destructive` is Ink (red belongs to VIPs), and `ring` is Ink (amber fails 3:1 on Paper).

## Conventions (follow them in our own components too)

- Plain function components taking `React.ComponentProps<...>`; React 19 passes `ref` as a prop, so no `forwardRef`.
- `data-slot="<component>-<part>"` on every element (`data-slot="ai-bubble"`), and reflect variants as `data-variant` / `data-size`, so parents can style children without prop drilling.
- Variants with `cva`; `className` goes last in `cn(...)` so callers win.
- State styling from attributes: `data-[state=open]:`, `aria-invalid:`, `aria-selected:`, `disabled:`. No `isOpen &&` class juggling.
- `asChild` (Radix Slot) to render a primitive as a link or our own element without wrapper divs.
- Radix exit animations must be CSS keyframes (Radix waits for `animationend`), not transitions.

## What to use for what (dashboard)

| Need | Use | Notes |
|---|---|---|
| Buttons | shadcn Button | Primary = amber fill, ink text. One primary per view |
| Side detail (conversation, client) | Sheet or a resizable pane (`react-resizable-panels`) | Not a modal |
| Confirm a destructive action | Prefer Undo in a toast; AlertDialog only when undo is impossible | Name the object and the consequence |
| Command palette (⌘K) | shadcn Command (cmdk 1.1) + Dialog | Bind ⌘K yourself. Server search: `shouldFilter={false}` with a loading row. VIP results never offer an AI reply |
| Notifications of the user's own async actions | sonner 2 via the shadcn wrapper, one `<Toaster>` | 4s, max 3 visible, Undo actions. See below |
| Mobile bottom sheet | shadcn Drawer (vaul 1.1.2) | vaul is **unmaintained**: pin exactly, use only via `components/ui/drawer.tsx`, mobile only, add a reduced-motion rule |
| Tables | shadcn Table + `@tanstack/react-table` | Sortable headers, sticky header, tabular numerals |
| Forms | shadcn Field + react-hook-form + zod | Errors inline under the field, never in a toast |
| Charts | shadcn Chart on Recharts 3 | Rules in `dashboard.md` |
| Dates | shadcn Calendar (react-day-picker 9) + date-fns 4 | Tenant time zone, dual clock for overseas buyers |

### When not to toast
- Validation errors (inline).
- Persistent states: channel disconnected, WhatsApp template rejected (banner or Alert).
- Incoming business events: new lead, VIP calling. These need a lasting surface; a VIP call never relies on a toast.
- Consent or opt-out recorded (show it on the contact).
- Success that is already visible on screen.

## Interaction craft (values from sonner and vaul source)

- Interruptible UI uses CSS transitions; keyframes only for mount and unmount.
- During drag, `transition: none` and follow the pointer 1:1; on release decide by distance **or** velocity (drawer: 25% or 0.4 px/ms; toast: 45px or 0.11 px/ms), then hand off to the eased transition.
- Rubber-band past the edges rather than stopping hard.
- Sheet easing `cubic-bezier(0.32, 0.72, 0, 1)` at 400-500ms; small UI 150-200ms.
- Don't start a drag within 500ms of opening or 100ms after the content scrolled.

## Marketing-only components (Magic UI)

Install through the shadcn registry: `npx shadcn@latest add @magicui/<name>`. Depends on `motion` (`motion/react`). Allowed, recoloured with tokens:
- **Marquee** (CSS only) for a logo or channel strip, once we have real logos.
- **NumberTicker** for proof stats, once we have real numbers. Patch it first: it renders `0` in static HTML and hardcodes `en-US` and colours. Render the final value, animate only after it is in view.
- **AnimatedBeam** for "every channel flows into one inbox".
- **BorderBeam** in sodium on a single highlighted card, rendered not at all under reduced motion.
- **DotPattern / GridPattern** at `text-ink/10` as a quiet architectural backdrop.
- **Safari / iPhone** frames around real dashboard screenshots.
- **BlurFade** at most once per section, never on the hero headline or the hero image (it starts invisible).

Avoid: globe (competes with the floor tour), particles, meteors, confetti, shimmer, rainbow or pulsating buttons, typing and word-rotate text, scroll-velocity and scroll-progress (the walk-through owns scroll). Only 2 of 80 Magic UI components handle reduced motion; wrap the app in `<MotionConfig reducedMotion="user">` and pause CSS loops under `motion-reduce`.

## Not adopted

daisyUI and Mantine. Both ship their own components and theme systems that collide with shadcn's classes, variables and focus styles. Ideas kept: foreground/background colour pairs, radius named by role, fixed control heights, Mantine's tinted "light" variant (which is exactly our AI and VIP chips), and reduced-motion handling on by default.
