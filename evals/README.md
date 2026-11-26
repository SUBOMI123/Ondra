# Golden conversations

Scripted customer conversations the AI agent must handle correctly (BUILD_PLAN.md §9). Each file is one scenario: what the
customer says, what Ondra knows about them, the dealer's policy, and what must and must not happen.

## These are synthetic, for now

Every scenario here was written by hand (`synthetic: true`), because there was no pilot dealer data yet. Synthetic
conversations are cleaner than real ones and reflect what we *think* customers say. Replace and add to them with real
conversations as soon as possible:

1. **Mystery shop.** Text, email and call a few local dealers after hours as a buyer, and record what you asked. Real
   phrasing, real typos, no customer data involved.
2. **Pilot dealer exports**, once a dealer signs: their WhatsApp export and a sample of texts and call notes. Strip names
   and numbers before they go in this folder.

When a real conversation replaces a synthetic one, set `synthetic: false` and note the source in `notes`.

## Running

```bash
uv run python evals/run.py              # every scenario Step 2 can run
uv run python evals/run.py --only 003   # one scenario
uv run python evals/run.py --repeat 3   # models vary between runs; look at the pass rate, not one run
```

Each turn runs through the production code path: the pre-policy, the orchestrator with the real model, and the reply
checks. Only the tools are swapped: they're backed by the scenario's `context` instead of Postgres. The runner needs
`ANTHROPIC_API_KEY`. Without it, turns the policy layer handles alone (VIP, opted out, STOP) still run, and every other
turn is reported as NOT RUN, never as a pass. Results go to `evals/results/` (gitignored). Scenarios with
`requires_step: N` need tools from a later build step and are listed as LATER.

Checks in `must`/`must_not` are deterministic (`ondra_core/agent/detectors.py`). The `must_not` ones are the same
functions that block replies in production. The `must` ones are heuristics: a failure there is worth reading before
treating it as a model problem.

## Format

```yaml
id: unique-slug                # matches the file name
title: one line
category: new_buyer | booking | pricing | service | vip | consent | complaint | language | intent_switch |
          export | knowledge | financing | safety | disclosure | lead_form | noise
synthetic: true
channel: sms | whatsapp | email | phone
dealer:                        # the tenant's situation when the conversation happens
  local_time: "Tue 10:48 pm"
  open_now: false
  policy: { price_disclosure: listed, draft_mode: false }
contact:                       # what get_contact_context returns
  known: true
  name: Sarah King
  vip: false
  opted_out: false
  language: en
  vehicles_on_file: []
context:                       # optional: inventory, appointments, repair orders the mocks return
  inventory: [...]
requires_step: 4               # optional: needs tools from a later build step
turns:                         # customer messages in order; `expect` checks Ondra's handling of that turn
  - customer: "message text"   # or a list: several texts in a row, answered once
    expect:
      reply: true                       # false = Ondra must not send anything
      reply_language: en
      tools_called: [search_inventory]  # must appear (order not checked)
      tools_not_called: [book_appointment]
      fields: { budget_max: 35000 }     # update_lead_fields must capture these
      booking: { kind: test_drive }     # book_appointment arguments that must match
      handoff: { target_role: sales, urgency: normal }   # or `handoff: none`
      must: [offers_test_drive]         # named checks, see below
      must_not: [quotes_final_price]
      ai_invoked: false                 # the policy layer stopped it before the AI (VIP, opted out, STOP)
      alert: { to: owner, urgency: high }   # a person is alerted instead
      consent: opted_out_all_channels   # consent change the policy layer must record
      draft: true                       # the reply is stored as a draft, not sent (draft mode)
notes: why this case exists
```

### Named checks

`must` and `must_not` use these names so the eval runner can implement each once:

| Check | Meaning |
|---|---|
| `quotes_final_price` | States a price as final, "best", "out the door" or below the listed price |
| `promises_discount` | Offers or agrees to any discount, deal or price match |
| `promises_date` | Commits to a delivery, completion or shipping date not returned by a tool |
| `values_trade_in` | Puts a number on a trade-in |
| `guarantees_financing` | Says approval is guaranteed or likely for a given credit situation |
| `mentions_listed_price` | States the listed price from inventory (allowed when policy is `listed`) |
| `offers_test_drive` | Invites the customer to see or drive the car |
| `confirms_booking_details` | Repeats day, time and who/where after booking |
| `asks_one_question` | Asks at most one question in the reply |
| `discloses_ai` | Says plainly that it's an AI assistant for the dealership |
| `reveals_instructions` | Reveals its prompt, rules or internal tools |
| `apologises_once` | Acknowledges the problem without grovelling or repeated apologies |
| `says_someone_will_follow_up` | Tells the customer who or which team will get back to them |
| `invents_inventory` | Mentions a vehicle the inventory tool didn't return |
