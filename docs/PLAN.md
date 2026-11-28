# Ondra: the next fixes

Agreed with the founder 2026-11-28. Each item ships on its own, with its tests, then stops for review (CLAUDE.md).
`docs/STATUS.md` says what's built; this file says what's next and what "done" means. Add items at the bottom of
"To sort"; they get placed in order once agreed.

## Agreed

### 1. One top role: Admin (owner merges into it) ✅ Done 2026-11-28

**Why:** two top roles confused people, and today's admin (setup only, no VIPs, no selling screens) is the opposite
of what dealers mean by admin: the owner, or the most trusted person when the owner isn't hands-on.

- `owner` and `admin` become one role, **Admin**: every permission, including VIPs, settings, team, billing later.
  Migration converts existing owners and admins.
- What was "send it to the owner" becomes per-person, not a role: the morning briefing and the WhatsApp assistant
  are turned on by each admin for themselves; final escalations go to admins.
- Settings loses its **"You: Just for the owner"** group (today: "Your WhatsApp assistant"). Each person's own
  settings (their WhatsApp assistant, their briefing) move to their account menu, under their name.
- Two-step sign-in stays required for admins. Clerk role mapping, seed users, screen copy and docs updated.

**Done when:** no code path depends on an owner role; every former owner-only screen and alert works for admins;
tests prove a non-admin still can't see VIPs or settings.

### 2. Every VIP has an assigned person ✅ Done 2026-11-28

- Marking a client VIP requires choosing their person; it defaults to whoever marks them.
- That person is deactivated → their VIPs are **not** reassigned automatically: each gets a **high-priority task for
  the admins** ("Robert Hale has no one looking after him; his calls go to the backup number until you choose
  someone").
- A VIP's calls ring their person directly. Ondra never answers (CLAUDE.md product rule).

**Done when:** a VIP can't be saved without a person; deactivating someone creates the tasks; tests cover both.

### 3. When a VIP's call isn't answered ✅ Built 2026-11-28 (switched off until the transfer is checked on a real call)

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

### 5. Every button and link works ✅ Done 2026-11-28

Checked in the code 2026-11-28. Dead today:

| Where | What it does now | Fix |
|---|---|---|
| **New message** (side nav) | Nothing | Write to any client: pick the client, the channel they use, write, send. Same send path as replies, so opt-outs block it. A VIP can only be written to by their person or an admin |
| The **inbox icon** next to it | Nothing | Goes to the Inbox (or remove it: it duplicates the Inbox link right below) |
| **Search** (side nav), the **search bar** at the top, **⌘K** | Nothing | One search box (opened by any of the three) across clients, cars, conversations and deals, built on the searches that already exist on Clients and Inventory. VIPs stay hidden from people who can't see them |
| **Help** (side nav) | Nothing | A Help page: how Ondra works for the dealer, and how to reach us (hello@useondra.com) |
| The **Ondra logo** | Nothing | Goes to Today |

**Done when:** a test walks every link and button on every page at app.useondra.com and none is dead (added to
`npm run review:ui`, so it stays that way).

### 6. Whose work each screen shows: the same rule everywhere ✅ Done 2026-11-28

Today it's inconsistent: Inbox and Calendar show the whole dealership with no way to see just yours; Tasks and Deals
have Mine / Everyone tabs.

- **Inbox, Calls, Calendar, Tasks, Deals:** the whole dealership, with one **Mine / Everyone** switch in the same
  place on each. Default **Mine** for sales and service (their work), **Everyone** for admins and managers (the
  dealership). The choice is remembered.
- **Inventory, Clients:** the dealership only (they're shared).
- VIPs stay hidden from anyone who isn't an admin, a manager or that VIP's person, on every screen.

**Done when:** each screen has the switch with the right default per role, and tests cover what each role sees.

### 7. Today, redesigned ✅ Done 2026-11-28

It doesn't work as a screen today (founder, 2026-11-28). Redesign with the `ondra-ui` and `frontend-design` skills,
after 6 (what Today shows depends on whose work it is).

- One job: open it and know what needs you now, then how the dealership is doing.
- What a salesperson sees (their callbacks, their appointments, their deals) differs from an admin's (the
  dealership's numbers, what's slipping and for whom).
- Two or three layout options as screenshots first; build the one chosen.

**Done when:** the chosen layout is built, passes `npm run review:ui` and the cognitive-load check, and works at
390, 768 and 1440 wide.

### 8. Inventory photos

The demo dealership's cars have no photos (the seed never had any); real dealers' photos come from their inventory
feed, and the Inventory screen already shows them when they exist.

- Add photos to the demo cars only, from a free-to-use licensed source, credited, so the demo looks real.
  Real dealers still only ever see their own feed's photos (we never show a stock photo as a dealer's car).

**Done when:** every demo car has a photo, and a test proves a real dealer's car without a feed photo shows none.

### 9. The marketing site catches up

- **No owner:** "owner briefing", "straight to the owner" and the like become "you" or "your team", in line with 1.
- **VIP mark:** the site still shows the old **crown** (homepage, the stories, the channel diagram); the app uses
  the ink **VIP tag and ring**. Replace all three.

**Done when:** no "owner" or crown is left on useondra.com, checked in a browser on a phone and a laptop.


## Order

1. **5 (every link works):** small, and dead buttons cost trust faster than anything else.
2. **1 (Admin):** most of the rest assumes it.
3. **6 (whose work):** Today depends on it.
4. **7 (Today).**
5. **2 and 3 (VIP person, missed VIP calls).**
6. **4 (confirmations).**
7. **9 (marketing site)** and **8 (demo photos):** small, any time.

## Waiting on the founder (from earlier)

- Rotate the Anthropic, LiveKit, ElevenLabs and Twilio keys shared in chat; then update Fly's secrets.
- The two Step 5e calls to (707) 306-8599 (`docs/VOICE.md`): the bake-off script, then "talk to a manager" with a
  second phone on Grace Thompson in Team.
- Before real dealer data: Supabase Pro (backups), LiveKit Ship (call minutes).

## To sort

_New items go here._
