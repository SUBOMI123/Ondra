/**
 * Example data for screens whose backend arrives in later steps (inbox and tasks in Step 3, deals in Step 3,
 * calendar in Step 4). Every page that uses it says "Example data" in its header. Names match the seed.
 */

export type Channel = "phone" | "sms" | "email" | "whatsapp"
export type Author = "customer" | "ondra" | "staff" | "system"

export type ThreadEvent =
  | { kind: "message"; author: Author; name?: string; body: string; time: string; channel?: Channel }
  | { kind: "call"; direction: "in" | "out"; time: string; duration: string; answeredBy: string; summary: string }
  | { kind: "event"; text: string; time: string; ai?: boolean }
  | { kind: "draft"; body: string; reason: string }

export type Conversation = {
  id: string
  /** Which inbox view it lives in: needs a person now, handled end to end by Ondra, or with the team. */
  bucket: "needs" | "ondra" | "team"
  /** Why it needs you, in plain words (only for bucket "needs"). */
  reason?: string
  client: string
  initials: string
  vip?: boolean
  channel: Channel
  time: string
  unread?: boolean
  snippet: string
  status: { kind: "ai" | "draft" | "vip" | "team" | "optout"; text: string }
  handledBy: "ondra" | "you" | "team"
  assignee?: string
  events: ThreadEvent[]
  brief?: string
  contact: { phone: string; email?: string; whatsapp?: boolean; language?: string }
  deal?: { vehicle: string; stock?: string; budget?: string; financing?: string; tradeIn?: string; timeline?: string; stage: string }
  tasks?: { title: string; due: string; overdue?: boolean }[]
  consent: { channel: string; status: string }[]
  upcoming?: { title: string; when: string }[]
}

export const CONVERSATIONS: Conversation[] = [
  {
    id: "kevin",
    bucket: "needs",
    reason: "Draft to approve",
    client: "Kevin Lee",
    initials: "KL",
    channel: "email",
    time: "9:41 pm",
    unread: true,
    snippet: "6:30 works. See you Thursday.",
    status: { kind: "ai", text: "Booked by Ondra" },
    handledBy: "ondra",
    assignee: "Daniel Okafor",
    brief:
      "Wants the gray 2022 Silverado LT and asked if the price is negotiable. Ondra didn't quote. Needs financing, no trade-in. Worth a call to pre-qualify before Thursday.",
    events: [
      { kind: "message", author: "customer", body: "Is the gray 2022 Silverado still available? Is the price negotiable? I'd need financing.", time: "9:12 pm", channel: "email" },
      { kind: "message", author: "ondra", body: "It's here: Silverado LT, 28k miles, listed at $44,900. Daniel can go through price and financing with you in person. Could you come by Thursday after work, say 6 pm?", time: "9:12 pm" },
      { kind: "call", direction: "in", time: "9:20 pm", duration: "1:12", answeredBy: "Ondra", summary: "Asked to move Thursday to 6:30. Confirmed he'll bring his license; no trade-in." },
      { kind: "event", text: "Test drive booked for Thursday, 6:30 pm, with Daniel", time: "9:21 pm", ai: true },
      { kind: "message", author: "customer", body: "6:30 works. See you Thursday.", time: "9:24 pm", channel: "email" },
      { kind: "draft", body: "Great, Kevin. The Silverado will be out front at 6:30 on Thursday. Want Daniel to start your credit application beforehand so you're not waiting at the desk?", reason: "Follow-ups need approval during your first week" },
    ],
    contact: { phone: "(214) 555-1000", email: "kevin.lee@example.com" },
    deal: { vehicle: "2022 Chevrolet Silverado LT", stock: "C22-1000", budget: "About $45,000", financing: "Needs it", tradeIn: "None", timeline: "This week", stage: "Appointment" },
    tasks: [{ title: "Call Kevin to pre-qualify", due: "Thu, 12:00 pm" }],
    consent: [
      { channel: "Email", status: "Replies allowed" },
      { channel: "Text", status: "Opted in, Nov 25" },
      { channel: "Calls", status: "Recording disclosed" },
    ],
    upcoming: [{ title: "Test drive with Daniel", when: "Thu, 6:30 pm" }],
  },
  {
    id: "robert",
    bucket: "needs",
    reason: "VIP called. Waiting 2 h",
    client: "Robert Hale",
    initials: "RH",
    vip: true,
    channel: "phone",
    time: "8:52 pm",
    unread: true,
    snippet: "Missed call. Rang your mobile.",
    status: { kind: "vip", text: "Waiting 2 h" },
    handledBy: "you",
    assignee: "Samuel Adeyemi",
    events: [
      { kind: "call", direction: "in", time: "8:52 pm", duration: "0:00", answeredBy: "No one", summary: "Rang your mobile for 30 seconds, then your office line. No voicemail left." },
      { kind: "event", text: "VIP alert sent to your phone", time: "8:53 pm" },
      { kind: "message", author: "customer", name: "Robert", body: "Sam, call me when you get a minute. It's about the Range Rover for my daughter.", time: "8:55 pm", channel: "sms" },
    ],
    contact: { phone: "(214) 555-1029", email: "robert.hale@example.com" },
    deal: { vehicle: "2024 Range Rover Sport", budget: "Not discussed", timeline: "Before Christmas", stage: "Qualified" },
    tasks: [{ title: "Call Robert back", due: "Today, 9:00 am", overdue: true }],
    consent: [
      { channel: "Text", status: "Opted in" },
      { channel: "Calls", status: "Recording off for VIPs" },
    ],
  },
  {
    id: "sarah",
    bucket: "needs",
    reason: "Draft to approve: trade-in",
    client: "Sarah King",
    initials: "SK",
    channel: "sms",
    time: "8:40 pm",
    snippet: "Do you take trade-ins on a 2019 Tahoe?",
    status: { kind: "draft", text: "Draft for you" },
    handledBy: "ondra",
    brief: "Asked about trading in a 2019 Tahoe toward the white Highlander. Ondra won't value trade-ins, so it drafted an offer of an appraisal on Saturday.",
    events: [
      { kind: "message", author: "customer", body: "Hi, is the white Highlander still there? Do you take trade-ins on a 2019 Tahoe?", time: "8:40 pm", channel: "sms" },
      { kind: "draft", body: "Hi Sarah, yes, the 2021 Highlander XLE is here. We take trade-ins and can appraise your Tahoe while you test drive. Would Saturday at 10 or 11 am work?", reason: "Trade-in questions need a person's OK (your policy)" },
    ],
    contact: { phone: "(214) 555-1001", email: "sarah.king@example.com" },
    deal: { vehicle: "2021 Toyota Highlander XLE", stock: "T21-1037", tradeIn: "2019 Chevrolet Tahoe", timeline: "This month", stage: "New" },
    consent: [{ channel: "Text", status: "Opted in, Nov 25" }],
  },
  {
    id: "marcus",
    bucket: "ondra",
    client: "Marcus Taylor",
    initials: "MT",
    channel: "phone",
    time: "7:05 pm",
    snippet: "Brakes squeaking, booked Wednesday.",
    status: { kind: "ai", text: "Booked by Ondra" },
    handledBy: "ondra",
    assignee: "Maria Lopez",
    brief: "Brakes squeaking on his 2019 F-150. Booked Bay 3 for Wednesday 7:30 am and requested a loaner.",
    events: [
      { kind: "call", direction: "in", time: "7:02 pm", duration: "2:41", answeredBy: "Ondra", summary: "Squeaking brakes on the 2019 F-150 on file. Booked Wednesday 7:30 am, Bay 3. Loaner requested." },
      { kind: "event", text: "Service booked for Wed 7:30 am, Bay 3, with Maria", time: "7:05 pm", ai: true },
      { kind: "message", author: "ondra", body: "You're booked for Wednesday at 7:30 am. A loaner will be ready. Reply C to confirm or R to reschedule.", time: "7:05 pm" },
      { kind: "message", author: "customer", body: "C", time: "7:10 pm", channel: "sms" },
    ],
    contact: { phone: "(214) 555-1002" },
    deal: { vehicle: "Service: brakes, 2019 F-150", stage: "Booked" },
    consent: [{ channel: "Text", status: "Opted in" }],
    upcoming: [{ title: "Service, Bay 3", when: "Wed, 7:30 am" }],
  },
  {
    id: "elena",
    bucket: "team",
    client: "Elena Ruiz",
    initials: "ER",
    channel: "whatsapp",
    time: "6:30 pm",
    snippet: "Is the 2020 RX certified pre-owned?",
    status: { kind: "team", text: "With Daniel" },
    handledBy: "team",
    assignee: "Daniel Okafor",
    brief: "Asked if the 2020 RX 350 is certified pre-owned. Daniel took over to confirm warranty terms.",
    events: [
      { kind: "message", author: "customer", body: "Hola, is the 2020 RX certified pre-owned?", time: "6:28 pm", channel: "whatsapp" },
      { kind: "message", author: "ondra", body: "Yes, it's a Lexus certified pre-owned RX 350. I'll have Daniel confirm the warranty details for you.", time: "6:28 pm" },
      { kind: "event", text: "Daniel took over from Ondra", time: "6:30 pm" },
      { kind: "message", author: "staff", name: "Daniel", body: "Hi Elena, it comes with the remaining factory warranty plus 2 years of CPO coverage. Want to see it this week?", time: "6:34 pm" },
    ],
    contact: { phone: "(214) 555-1003", whatsapp: true, language: "Spanish and English" },
    deal: { vehicle: "2020 Lexus RX 350", stock: "L20-1172", stage: "Qualified" },
    consent: [{ channel: "WhatsApp", status: "Opted in" }],
  },
  {
    id: "jordan",
    bucket: "team",
    client: "Jordan Price",
    initials: "JP",
    channel: "sms",
    time: "5:12 pm",
    snippet: "STOP",
    status: { kind: "optout", text: "Opted out" },
    handledBy: "team",
    events: [
      { kind: "message", author: "ondra", body: "Hi Jordan, the Civic you asked about is still here. Want to take it for a drive this week?", time: "5:10 pm" },
      { kind: "message", author: "customer", body: "STOP", time: "5:12 pm", channel: "sms" },
      { kind: "event", text: "Opted out. Ondra and your team can't send Jordan anything on any channel.", time: "5:12 pm" },
    ],
    contact: { phone: "(214) 555-1004" },
    consent: [{ channel: "All channels", status: "Opted out, Nov 25" }],
  },
  {
    id: "priya",
    bucket: "ondra",
    client: "Priya Shah",
    initials: "PS",
    channel: "email",
    time: "4:48 pm",
    snippet: "Booked a RAV4 Hybrid test drive for Saturday.",
    status: { kind: "ai", text: "Booked by Ondra" },
    handledBy: "ondra",
    assignee: "Daniel Okafor",
    brief: "First car, pre-approved with her credit union. Booked a test drive Saturday 10 am.",
    events: [
      { kind: "message", author: "customer", body: "Hi, could I test drive the RAV4 Hybrid this weekend? I'm pre-approved with my credit union.", time: "4:41 pm", channel: "email" },
      { kind: "message", author: "ondra", body: "Of course. Saturday at 10 am or 1 pm work. Which suits you? Bring your pre-approval letter and Daniel can go through the numbers.", time: "4:41 pm" },
      { kind: "message", author: "customer", body: "10 am please.", time: "4:46 pm", channel: "email" },
      { kind: "event", text: "Test drive booked for Saturday, 10:00 am, with Daniel", time: "4:46 pm", ai: true },
    ],
    contact: { phone: "(214) 555-1007", email: "priya.shah@example.com" },
    deal: { vehicle: "2024 Toyota RAV4 Hybrid", financing: "Pre-approved", timeline: "This weekend", stage: "Appointment" },
    consent: [{ channel: "Email", status: "Replies allowed" }],
    upcoming: [{ title: "Test drive with Daniel", when: "Sat, 10:00 am" }],
  },
  {
    id: "luis",
    bucket: "ondra",
    client: "Luis Romero",
    initials: "LR",
    channel: "sms",
    time: "3:15 pm",
    snippet: "60k-mile service booked for Thursday.",
    status: { kind: "ai", text: "Booked by Ondra" },
    handledBy: "ondra",
    assignee: "Maria Lopez",
    brief: "60,000-mile service on his 2020 Tacoma. Booked Thursday 8 am, Bay 1. He'll wait in the lounge.",
    events: [
      { kind: "message", author: "customer", body: "Need my 60k service on the Tacoma. Thursday morning?", time: "3:12 pm", channel: "sms" },
      { kind: "message", author: "ondra", body: "Thursday at 8 am is open. It takes about 2 hours. Will you wait with us or need a ride?", time: "3:12 pm" },
      { kind: "message", author: "customer", body: "I'll wait.", time: "3:14 pm", channel: "sms" },
      { kind: "event", text: "Service booked for Thu 8:00 am, Bay 1, with Maria", time: "3:15 pm", ai: true },
    ],
    contact: { phone: "(214) 555-1008" },
    deal: { vehicle: "Service: 60k-mile, 2020 Tacoma", stage: "Booked" },
    consent: [{ channel: "Text", status: "Opted in" }],
    upcoming: [{ title: "Service, Bay 1", when: "Thu, 8:00 am" }],
  },
]

export type TaskCard = {
  title: string
  client: string
  source: "handoff" | "rule" | "manual"
  assignee: string
  due: string
  overdue?: boolean
  escalated?: boolean
  brief?: string
}

export const TASKS: Record<"open" | "in_progress" | "done", TaskCard[]> = {
  open: [
    { title: "Call Robert back", client: "Robert Hale", source: "rule", assignee: "Samuel Adeyemi", due: "Today, 9:00 am", overdue: true, escalated: true, brief: "VIP missed call last night. Asked about a Range Rover for his daughter." },
    { title: "Approve trade-in reply", client: "Sarah King", source: "handoff", assignee: "Daniel Okafor", due: "Today, 10:30 am", brief: "Ondra drafted an appraisal offer. Trade-in questions need your OK." },
    { title: "Send 3 options under $65k", client: "Aisha Bello", source: "handoff", assignee: "Daniel Okafor", due: "Today, 12:00 pm", brief: "Black or dark grey GLE, before the holidays." },
    { title: "Confirm parts for recall", client: "Mei Chen", source: "rule", assignee: "Maria Lopez", due: "Tomorrow, 8:00 am" },
  ],
  in_progress: [
    { title: "Call Kevin to pre-qualify", client: "Kevin Lee", source: "handoff", assignee: "Daniel Okafor", due: "Thu, 12:00 pm", brief: "Needs financing, no trade-in. Test drive Thursday 6:30 pm." },
    { title: "Confirm CPO warranty terms", client: "Elena Ruiz", source: "manual", assignee: "Daniel Okafor", due: "Today, 3:00 pm" },
    { title: "Payment estimate for CR-V", client: "Natalie Ross", source: "handoff", assignee: "Chris Bell", due: "Today, 1:00 pm", overdue: true },
  ],
  done: [
    { title: "Book loaner for Marcus", client: "Marcus Taylor", source: "rule", assignee: "Maria Lopez", due: "Done 7:20 pm" },
    { title: "Delivery paperwork", client: "Darnell Brooks", source: "manual", assignee: "Chris Bell", due: "Done 4:05 pm" },
  ],
}

export type DealCard = { client: string; vehicle: string; value: number; owner: string; channel: Channel; byOndra?: boolean; vip?: boolean; note?: string }

export const SALES_STAGES: { stage: string; deals: DealCard[] }[] = [
  { stage: "New", deals: [
    { client: "Aisha Bello", vehicle: "2023 Mercedes-Benz GLE 450", value: 64000, owner: "Daniel", channel: "whatsapp", byOndra: true },
    { client: "Hannah Weiss", vehicle: "2023 Tesla Model Y", value: 41000, owner: "Unassigned", channel: "email", byOndra: true },
    { client: "Sarah King", vehicle: "2021 Toyota Highlander XLE", value: 33900, owner: "Daniel", channel: "sms", byOndra: true, note: "Trade-in: 2019 Tahoe" },
  ] },
  { stage: "Qualified", deals: [
    { client: "Robert Hale", vehicle: "2024 Range Rover Sport", value: 92000, owner: "You", channel: "phone", vip: true },
    { client: "Elena Ruiz", vehicle: "2020 Lexus RX 350", value: 36500, owner: "Daniel", channel: "whatsapp", byOndra: true },
    { client: "Natalie Ross", vehicle: "2024 Honda CR-V Hybrid", value: 37200, owner: "Chris", channel: "email", byOndra: true },
  ] },
  { stage: "Appointment", deals: [
    { client: "Kevin Lee", vehicle: "2022 Chevrolet Silverado LT", value: 44900, owner: "Daniel", channel: "email", byOndra: true, note: "Thu 6:30 pm" },
    { client: "Priya Shah", vehicle: "2024 Toyota RAV4 Hybrid", value: 34800, owner: "Daniel", channel: "email", byOndra: true, note: "Sat 10:00 am" },
    { client: "Omar Haddad", vehicle: "2022 Lexus ES 350", value: 38200, owner: "Daniel", channel: "whatsapp", byOndra: true, note: "Video walkaround Mon" },
  ] },
  { stage: "Test drive done", deals: [
    { client: "Tom Nguyen", vehicle: "2022 Ford Bronco Badlands", value: 47500, owner: "Chris", channel: "phone" },
    { client: "Samuel Bakare", vehicle: "2023 Toyota Sequoia", value: 71000, owner: "You", channel: "whatsapp" },
  ] },
  { stage: "Negotiating", deals: [
    { client: "Grace Kim", vehicle: "2021 BMW X5 xDrive40i", value: 48900, owner: "Chris", channel: "phone", byOndra: true },
  ] },
  { stage: "Sold", deals: [
    { client: "Darnell Brooks", vehicle: "2022 Chevrolet Tahoe Z71", value: 58400, owner: "Chris", channel: "sms", note: "Delivery Fri" },
  ] },
]

export const SERVICE_STAGES: { stage: string; deals: DealCard[] }[] = [
  { stage: "Booked", deals: [
    { client: "Marcus Taylor", vehicle: "Brakes, 2019 F-150", value: 480, owner: "Maria", channel: "phone", byOndra: true, note: "Wed 7:30 am, Bay 3" },
    { client: "Luis Romero", vehicle: "60k-mile service, 2020 Tacoma", value: 690, owner: "Maria", channel: "sms", byOndra: true, note: "Thu 8:00 am, Bay 1" },
    { client: "Mei Chen", vehicle: "Recall, 2019 CR-V", value: 0, owner: "Maria", channel: "phone", byOndra: true, note: "Tue 9:00 am, Bay 2" },
  ] },
  { stage: "In service", deals: [
    { client: "Ethan Walker", vehicle: "Transmission check, 2018 Accord", value: 320, owner: "Maria", channel: "phone" },
  ] },
  { stage: "Ready", deals: [
    { client: "Rachel Green", vehicle: "4 tires, 2021 Camry", value: 860, owner: "Maria", channel: "phone", byOndra: true, note: "Invoice sent" },
  ] },
  { stage: "Picked up", deals: [
    { client: "Fatima Hassan", vehicle: "Oil change, 2022 RAV4", value: 89, owner: "Maria", channel: "sms" },
  ] },
]
