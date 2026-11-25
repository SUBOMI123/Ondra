# AI provenance and VIPs

These are the product rules from `CLAUDE.md` made visible. Get them wrong and the UI lies to the dealer.

## Anything the AI did

- **Colour:** `bg-ai-subtle text-ai border-ai-border`. Nothing else in the product uses blue.
- **Label:** always name the actor in words, next to the content: "Drafted by Ondra", "Sent by Ondra", "Booked by Ondra", "Summary by Ondra". Icon `IconSparkles` at 16px before the word. Colour is never the only signal.
- **Lifecycle of an AI message** (one component, `data-slot="ai-bubble"`, `data-state` drives the look):

| State | Look | Actions |
|---|---|---|
| `drafting` | Ondra-blue outline, skeleton lines, "Ondra is writing…" | Stop |
| `awaiting-approval` | Ondra-blue surface, dashed border, "Draft by Ondra, waiting for you" | Send, Edit, Discard |
| `sent` | Ondra-blue surface, solid, "Sent by Ondra · 2:14 am" laid out as two parts, not a dot string | View reasoning (later) |
| `edited` | Once a person edits and sends it, it becomes a normal staff message with a small "Edited from Ondra's draft" note in muted text | — |
| `handed-off` | Neutral row: "Ondra passed this to Daniel (Sales)", the brief in a quote block, the deadline | Open brief |

- **Draft mode** (first week per tenant): every AI reply arrives as `awaiting-approval`. The Inbox shows a persistent banner, not a toast: "Draft mode is on. Ondra writes, you approve."
- **Bookings and tasks created by the AI** carry the same blue tag in the calendar and task board. A person changing them removes the tag.
- **Call records:** transcript turns by the voice agent in Ondra blue, the caller in the default text colour. The summary card is Ondra blue and labelled.
- **Never** show the AI committing to a final price, discount or delivery date in sample content. Sample AI replies hand those to a person.

## VIPs

- **Mark:** `IconCrownFilled` with `text-vip`, and a `bg-vip-subtle text-vip` pill reading "VIP". Same on every surface.
- **No AI anywhere near them:** a VIP thread renders no Ondra-blue element, no draft, no "Let Ondra reply", no AI summary, no suggested reply. The composer is the person's own. A test should assert this (`[data-vip] [data-slot^="ai-"]` must match nothing).
- **Calls:** "Rings you directly" on the contact; missed VIP calls go to a "Needs you" list at the top of Today in VIP red, not to a toast.
- **Waiting messages:** shown with time waiting ("Waiting 2 h") so the owner sees the cost of delay. Overdue uses VIP red too; that is its only other use.
- VIPs count in totals but no chart singles one out by name.

## Consent and opt-outs

- An opted-out contact shows a persistent neutral badge "Opted out (STOP) · all channels", laid out as label plus detail, and the composer is disabled with the reason. Not red: it is a state, not an alarm.
- Outbound actions without recorded consent are disabled with a one-line explanation and a link to record consent.
- Recording disclosure state is visible on the call record ("Recording notice played").

## Marketing representations

The landing page may show the AI at work (the floor labels, sample threads), but sample content follows the same rules: AI replies labelled, no price or delivery promises, the VIP shown going to the owner. Mark examples as examples where a reader could mistake them for a real dealer's data.
