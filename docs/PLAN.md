# Ondra: the next fixes

Agreed with the founder 2026-11-28. Each item ships on its own, with its tests, then stops for review (CLAUDE.md).
`docs/STATUS.md` says what's built; this file says what's next and what "done" means. Add items at the bottom of
"To sort"; they get placed in order once agreed.

## Agreed

### 1. One top role: Admin (owner merges into it)

**Why:** two top roles confused people, and today's admin (setup only, no VIPs, no selling screens) is the opposite
of what dealers mean by admin: the owner, or the most trusted person when the owner isn't hands-on.

- `owner` and `admin` become one role, **Admin**: every permission, including VIPs, settings, team, billing later.
  Migration converts existing owners and admins.
- What was "send it to the owner" becomes per-person, not a role: the morning briefing and the WhatsApp assistant
  are turned on by each admin for themselves; final escalations go to admins.
- Two-step sign-in stays required for admins. Clerk role mapping, seed users, screen copy and docs updated.

**Done when:** no code path depends on an owner role; every former owner-only screen and alert works for admins;
tests prove a non-admin still can't see VIPs or settings.

### 2. Every VIP has an assigned person

- Marking a client VIP requires choosing their person; it defaults to whoever marks them.
- That person is deactivated → their VIPs are **not** reassigned automatically: each gets a **high-priority task for
  the admins** ("Robert Hale has no one looking after him; his calls go to the backup number until you choose
  someone").
- A VIP's calls ring their person directly. Ondra never answers (CLAUDE.md product rule).

**Done when:** a VIP can't be saved without a person; deactivating someone creates the tasks; tests cover both.

### 3. When a VIP's call isn't answered

| Step | What happens |
|---|---|
| Their person's phone rings (~20 s) | The relationship they know |
| No answer: a **fixed message, in the dealer's own words** (Settings), never the AI | "Sorry we missed you, Robert. Daniel's been told and will call you back shortly. If it's urgent, press 1. To book a time yourself, press 2 and we'll text you a link." |
| **Press 1** | Rings **one backup number**: the front desk or a backup person the dealer chooses (not every admin) |
| **Press 2** | A fixed text with a self-serve booking link. Only offered where text consent is on file until counsel answers (below) |
| In parallel, at once | Urgent alert to their person ("Robert Hale just called"), high-priority callback task |

- The backup number must be a phone a human answers, never the dealer's main line (that forwards to Ondra: a VIP
  would loop back to the AI).
- **Counsel question:** does a caller pressing 2 to ask for the link count as consent for that one text?

**Done when:** on every path (answered, unanswered, press 1, press 2, hang up) tests prove the AI never speaks to the
VIP, the person is alerted, and a task exists for every call not answered by a person.

### 4. Booking confirmations

| | Rule |
|---|---|
| Main confirmation | On the customer's channel (where they booked, or their preferred one): WhatsApp, text or email |
| Email copy | Whenever we have their email, with a **calendar invite (.ics)** attached |
| Every message | **"Add to calendar"** (Apple, Google, Outlook) and a link to reschedule or cancel |
| Booked in a text thread | The AI's reply already confirmed it; the email copy with the invite still goes |
| Reschedule / cancel | Same rule; the calendar invite updates |

- At most two messages per booking. Consent and opt-outs as everywhere: no consent on a channel, no message there,
  and staff see why ("No confirmation text: no consent on file").
- **VIPs:** no automated confirmation; their person gets a task to confirm personally.
- Quiet hours: a booking made at 10 pm confirms at 8 am.
- WhatsApp outside the 24-hour window needs a Meta-approved template: submitted with the briefing and alert templates.

**Done when:** tests cover each source (AI chat, AI call, staff calendar, booking link), each channel, no consent,
opt-out, VIP and reschedule; the .ics opens in Google, Apple and Outlook calendars.

**Estimate for 1–4:** about 2.5–3 days.

## Waiting on the founder (from earlier)

- Rotate the Anthropic, LiveKit, ElevenLabs and Twilio keys shared in chat; then update Fly's secrets.
- The two Step 5e calls to (707) 306-8599 (`docs/VOICE.md`): the bake-off script, then "talk to a manager" with a
  second phone on Grace Thompson in Team.
- Before real dealer data: Supabase Pro (backups), LiveKit Ship (call minutes).

## To sort

_New items go here._
