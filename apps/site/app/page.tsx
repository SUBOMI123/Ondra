import DemoForm from "@/components/DemoForm";
import Walkthrough from "@/components/Walkthrough";
import { CONTACT_EMAIL } from "@/lib/config";

export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Channels />
        <Problem />
        <Walkthrough />
        <Agents />
        <WhatsApp />
        <Vip />
        <OwnerBriefing />
        <Guardrails />
        <Setup />
        <Fit />
        <Demo />
        <Faq />
      </main>
      <Footer />
    </>
  );
}

function Wrap({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-[1200px] px-4 sm:px-7 ${className}`}>{children}</div>;
}

function H2({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <h2 className={`x text-[clamp(30px,4vw,52px)] font-bold leading-[1.04] tracking-[-0.01em] ${className}`}>{children}</h2>
  );
}

function Logo({ className = "" }: { className?: string }) {
  return (
    <a href="#top" className={`x flex items-center gap-2.5 text-xl font-bold no-underline ${className}`}>
      <i aria-hidden="true" className="block size-[11px] rounded-full bg-sodium" />
      Ondra
    </a>
  );
}

/* ---------------------------------------------------------------- nav */

function Nav() {
  return (
    <header className="absolute inset-x-0 top-0 z-30">
      <Wrap className="flex items-center justify-between py-5 text-white">
        <Logo />
        <nav aria-label="Main" className="flex items-center gap-6 text-[15px]">
          <a href="#how" className="hidden no-underline opacity-85 hover:opacity-100 md:inline">
            How it works
          </a>
          <a href="#whatsapp" className="hidden no-underline opacity-85 hover:opacity-100 md:inline">
            WhatsApp
          </a>
          <a href="#vip" className="hidden no-underline opacity-85 hover:opacity-100 md:inline">
            VIPs
          </a>
          <a href="#faq" className="hidden no-underline opacity-85 hover:opacity-100 md:inline">
            FAQ
          </a>
          <a href="#demo" className="btn btn-primary !min-h-[42px] !px-4">
            Book a demo
          </a>
        </nav>
      </Wrap>
    </header>
  );
}

/* ---------------------------------------------------------------- hero */

function Hero() {
  return (
    <section
      id="top"
      className="relative overflow-hidden bg-ink text-white"
      style={{
        // Photo is optional: drop the pilot dealer's showroom (with permission) at public/exterior.jpg.
        // Until then the gradient alone carries the hero.
        backgroundImage:
          "linear-gradient(0deg, rgba(10,10,12,.92) 0%, rgba(10,10,12,.55) 55%, rgba(10,10,12,.75) 100%), radial-gradient(120% 80% at 80% 0%, rgba(242,163,58,.22), transparent 60%), url(/exterior.jpg)",
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      <Wrap className="grid items-end gap-12 pb-16 pt-32 sm:pb-24 sm:pt-40 lg:grid-cols-[1.15fr_1fr] lg:gap-16">
        <div>
          <p className="eyebrow text-sodium">AI staff for car dealerships</p>
          <h1 className="x mt-4 max-w-[12ch] text-[clamp(44px,7vw,96px)] font-bold leading-[0.95] tracking-[-0.02em]">
            Your dealership, fully staffed.
          </h1>
          <p className="mt-6 max-w-[46ch] text-[19px] leading-relaxed text-[#E4E5EA]">
            Ondra answers every call, WhatsApp, text and email in seconds, day or night. It qualifies the buyer, books
            the visit and hands the deal to the right person on your team.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="#demo" className="btn btn-primary">
              Book a demo
            </a>
            <a href="#how" className="btn btn-line">
              See how it works
            </a>
          </div>
          <p className="mt-6 text-sm text-[#B9BBC2]">
            Keep your phone number, WhatsApp and email. Your customers never see a new one.
          </p>
        </div>
        <HeroThread />
      </Wrap>
    </section>
  );
}

function HeroThread() {
  return (
    <figure
      aria-label="Example: Ondra replying to a buyer on WhatsApp at night"
      className="mx-auto w-full max-w-[440px] rounded-2xl bg-[#ECE5DD] p-4 text-ink shadow-[0_30px_60px_-20px_rgba(0,0,0,.6)]"
    >
      <div className="flex items-center justify-between border-b border-black/10 pb-3">
        <div>
          <p className="text-[15px] font-semibold">Chidi O. · Lagos</p>
          <p className="text-xs text-muted">WhatsApp · 2:14 am in Dallas</p>
        </div>
        <span className="rounded-full bg-wa px-2.5 py-1 text-[11px] font-semibold text-white">WhatsApp</span>
      </div>
      <div className="space-y-2.5 pt-3 text-[14.5px] leading-snug">
        <p className="max-w-[85%] rounded-lg rounded-tl-none bg-white px-3 py-2">
          Good evening. Is the black 2023 G63 still available? Can you ship to Lagos?
        </p>
        <p className="ml-auto max-w-[88%] rounded-lg rounded-tr-none bg-[#D9FDD3] px-3 py-2">
          Yes, it&apos;s on the lot: black, 18k miles. We ship to Lagos regularly. Would a live video walkaround help?
          Daniel can do Thursday at 10am Dallas time, that&apos;s 4pm for you.
        </p>
        <p className="max-w-[60%] rounded-lg rounded-tl-none bg-white px-3 py-2">Thursday works. Please book it.</p>
        <p className="ml-auto max-w-[70%] rounded-lg rounded-tr-none bg-[#D9FDD3] px-3 py-2">
          Booked. Daniel will call you on WhatsApp video. 👍
        </p>
      </div>
      <figcaption className="mt-3 rounded-lg bg-ai-bg px-3 py-2.5 text-[12.5px] text-ai">
        <b className="font-semibold">Ondra</b> · Lead qualified: G63, budget ~$180k, wire transfer, ships to Lagos ·
        Video walkaround booked · Brief sent to Daniel (Sales)
      </figcaption>
    </figure>
  );
}

function Channels() {
  const items = [
    { name: "Phone", note: "Voice agent" },
    { name: "WhatsApp", note: "Official Business API" },
    { name: "SMS", note: "Texts" },
    { name: "Email", note: "Your own inbox" },
    { name: "Instagram", note: "Coming later" },
  ];
  return (
    <section aria-label="Channels" className="border-b border-line bg-paper">
      <Wrap className="flex flex-wrap items-center justify-between gap-x-8 gap-y-4 py-7">
        <p className="text-sm font-semibold text-muted">Every channel, one inbox:</p>
        <ul className="flex flex-wrap gap-x-8 gap-y-3">
          {items.map((i) => (
            <li key={i.name} className="flex items-baseline gap-2">
              <span className="x text-lg font-bold">{i.name}</span>
              <span className="text-[13px] text-muted">{i.note}</span>
            </li>
          ))}
        </ul>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- problem */

function Problem() {
  const items = [
    {
      t: "The phone rings at 7:40pm.",
      p: "The showroom is closed, so the buyer calls the next dealer on the list. You never know the call happened.",
    },
    {
      t: "The WhatsApp lives on someone's phone.",
      p: "Leads sit in a salesperson's personal chat. Nobody else can see them, follow up or pick them up when that person is off.",
    },
    {
      t: "Your best buyer is in another time zone.",
      p: "Buyers in Lagos, Accra and Dubai message while Dallas sleeps. By the time you reply, they've asked three other dealers.",
    },
  ];
  return (
    <section className="bg-paper py-24 sm:py-32">
      <Wrap>
        <H2 className="max-w-[20ch]">Buyers don&apos;t wait. Most dealerships make them.</H2>
        <ol className="mt-12 grid gap-10 md:grid-cols-3">
          {items.map((i) => (
            <li key={i.t} className="border-t-2 border-ink pt-5">
              <b className="x block text-[21px] leading-tight">{i.t}</b>
              <p className="mt-3 text-[16px] leading-relaxed text-ink-2">{i.p}</p>
            </li>
          ))}
        </ol>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- agents */

function Agents() {
  const agents = [
    {
      role: "Voice agent",
      name: "Reception",
      p: "Picks up every call, after hours or as backup when your team is busy. Answers from your inventory and your own answers, and records and transcribes every call.",
    },
    {
      role: "Messaging agent",
      name: "WhatsApp, SMS and email",
      p: "Replies in seconds with photos, specs and availability, and asks the questions your salespeople would ask.",
    },
    {
      role: "Booking agent",
      name: "Test drives and visits",
      p: "Books showroom visits, test drives and video walkarounds against your team's real calendars. One calendar, no double-booking.",
    },
    {
      role: "Service agent",
      name: "Service desk",
      p: "Books service into real bay capacity, using the appointment types you set up.",
    },
    {
      role: "Routing agent",
      name: "Handoffs",
      p: "Sends each conversation to the right person in sales, service, logistics or to you, with a short brief and a deadline.",
    },
    {
      role: "Follow-up agent",
      name: "Follow-ups",
      p: "Drafts reminders and nudges for buyers who went quiet, and waits for your approval before sending.",
    },
  ];
  return (
    <section id="how" className="scroll-mt-4 bg-paper py-24 sm:py-32">
      <Wrap>
        <p className="eyebrow text-muted">How it works</p>
        <H2 className="mt-3 max-w-[18ch]">Six agents. One calendar. Your rules.</H2>
        <p className="mt-5 max-w-[60ch] text-[18px] leading-relaxed text-ink-2">
          Every conversation becomes a client profile with the vehicle, budget, destination, timeline and payment
          method filled in. Your team works from one inbox with every call recording, transcript and message.
        </p>
        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((a) => (
            <li key={a.name} className="rounded-xl border border-line bg-white p-6">
              <span className="flex items-center gap-2 text-[13px] text-muted">
                <i aria-hidden="true" className="block size-2 rounded-full bg-[#3B7BF0]" />
                {a.role}
              </span>
              <b className="x mt-1.5 block text-[20px] leading-tight">{a.name}</b>
              <p className="mt-3 text-[15.5px] leading-relaxed text-ink-2">{a.p}</p>
            </li>
          ))}
          <li className="rounded-xl border border-vip/25 bg-vip-bg p-6 sm:col-span-2 lg:col-span-3">
            <span className="flex items-center gap-2 text-[13px] text-vip">
              <i aria-hidden="true" className="block size-2 rounded-full bg-vip" />
              Not an agent
            </span>
            <b className="x mt-1.5 block text-[20px] leading-tight text-vip">Your office</b>
            <p className="mt-3 max-w-[70ch] text-[15.5px] leading-relaxed text-ink-2">
              VIP clients skip the agents completely. Their calls ring you and their messages wait for you.
            </p>
          </li>
        </ul>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- whatsapp / cross-border */

function WhatsApp() {
  const points = [
    {
      t: "Your number, the official API",
      p: "Ondra connects your existing WhatsApp Business number through Meta's official API. No grey-market tools that get numbers banned.",
    },
    {
      t: "Their time zone, your calendar",
      p: "Buyers are answered at their 2am, and bookings land in your working hours. Every time is shown in both zones.",
    },
    {
      t: "Export questions, captured",
      p: "Destination, payment method, timeline and budget go straight into the client profile, so your team starts the call already knowing the deal.",
    },
    {
      t: "No DMS? No problem",
      p: "If you run on WhatsApp and a spreadsheet, Ondra is your CRM. If you have a DMS or CRM, we'll work with you to connect it.",
    },
  ];
  return (
    <section id="whatsapp" className="scroll-mt-4 bg-ink py-24 text-white sm:py-32">
      <Wrap>
        <p className="eyebrow text-sodium">WhatsApp-first</p>
        <H2 className="mt-3 max-w-[20ch]">Built for buyers who live on WhatsApp.</H2>
        <p className="mt-5 max-w-[60ch] text-[18px] leading-relaxed text-[#C9CBD1]">
          Most dealer AI tools are built for US buyers on phone and text. Ondra is built for dealers whose buyers are in
          Lagos, Accra, Dubai or down the road, and who would rather message than call.
        </p>
        <ul className="mt-12 grid gap-x-10 gap-y-10 md:grid-cols-2">
          {points.map((i) => (
            <li key={i.t} className="border-t border-white/25 pt-5">
              <b className="x block text-[20px]">{i.t}</b>
              <p className="mt-2.5 text-[16px] leading-relaxed text-[#C9CBD1]">{i.p}</p>
            </li>
          ))}
        </ul>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- VIP */

function Vip() {
  return (
    <section id="vip" className="scroll-mt-4 bg-paper py-24 sm:py-32">
      <Wrap className="grid items-center gap-12 lg:grid-cols-2">
        <div>
          <p className="eyebrow text-vip">VIPs</p>
          <H2 className="mt-3 max-w-[16ch]">Some clients should never talk to a bot.</H2>
          <p className="mt-5 max-w-[50ch] text-[18px] leading-relaxed text-ink-2">
            Mark a client, or the people who buy for them, as VIP. Their calls ring you directly. Their messages wait
            for your personal reply. No AI answer, no AI draft, no voice agent, ever.
          </p>
          <p className="mt-4 max-w-[50ch] text-[16px] leading-relaxed text-muted">
            If you miss the call, you get an alert straight away, not a summary at the end of the day.
          </p>
        </div>
        <div aria-hidden="true" className="mx-auto w-full max-w-[420px] space-y-3">
          <div className="rounded-xl border border-vip/25 bg-white p-5 shadow-[0_20px_40px_-24px_rgba(0,0,0,.35)]">
            <div className="flex items-center justify-between">
              <span className="rounded-full bg-vip-bg px-2.5 py-1 text-[12px] font-semibold text-vip">VIP</span>
              <span className="text-[12px] text-muted">Incoming call</span>
            </div>
            <p className="x mt-3 text-[22px] font-bold">Alhaji M.</p>
            <p className="text-[14px] text-muted">Ringing your mobile, skipping the voice agent</p>
            <div className="mt-4 flex gap-2">
              <span className="flex-1 rounded-md bg-[#1F7A4D] py-2.5 text-center text-sm font-semibold text-white">
                Answer
              </span>
              <span className="flex-1 rounded-md border border-line py-2.5 text-center text-sm font-semibold">
                Text back
              </span>
            </div>
          </div>
          <div className="rounded-xl border border-line bg-white p-4 text-[14px]">
            <p className="font-semibold">WhatsApp from Alhaji M.&apos;s manager</p>
            <p className="mt-1 text-muted">Waiting for you · AI replies off for this contact</p>
          </div>
        </div>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- owner on WhatsApp */

function OwnerBriefing() {
  return (
    <section className="border-y border-line bg-paper-2 py-24 sm:py-32">
      <Wrap className="grid items-center gap-12 lg:grid-cols-[1fr_1.05fr]">
        <div aria-hidden="true" className="order-2 mx-auto w-full max-w-[420px] rounded-2xl bg-[#ECE5DD] p-4 lg:order-1">
          <p className="pb-2 text-center text-[12px] text-muted">Today 7:30 am</p>
          <div className="max-w-[92%] rounded-lg rounded-tl-none bg-white px-3.5 py-3 text-[14.5px] leading-relaxed">
            <p className="font-semibold">Good morning. Here&apos;s today:</p>
            <ul className="mt-1.5 space-y-0.5">
              <li>🔴 2 VIPs waiting for you</li>
              <li>🔥 5 hot leads overnight, 3 from Nigeria</li>
              <li>✍️ 4 follow-ups ready to approve</li>
              <li>📅 3 test drives, 1 video walkaround, 6 service bookings</li>
            </ul>
            <div className="mt-3 grid grid-cols-2 gap-2 border-t border-black/10 pt-2.5 text-center text-[14px] font-semibold text-[#027EB5]">
              <span>Approve all 4</span>
              <span>Review</span>
            </div>
          </div>
          <div className="ml-auto mt-2.5 flex max-w-[70%] items-center gap-2 rounded-lg rounded-tr-none bg-[#D9FDD3] px-3 py-2.5 text-[13px]">
            <span>▶︎</span>
            <span className="h-1 flex-1 rounded bg-black/20" />
            <span className="text-muted">0:14</span>
          </div>
          <div className="mt-2.5 max-w-[85%] rounded-lg rounded-tl-none bg-white px-3.5 py-2.5 text-[14px]">
            Got it. Task for Daniel: send Chidi the shipping quote by 3pm. Chidi&apos;s profile is updated.
          </div>
        </div>
        <div className="order-1 lg:order-2">
          <p className="eyebrow text-muted">For the owner</p>
          <H2 className="mt-3 max-w-[16ch]">Run your morning from WhatsApp.</H2>
          <p className="mt-5 max-w-[50ch] text-[18px] leading-relaxed text-ink-2">
            A briefing before you get to the lot: who&apos;s waiting, what came in overnight, what&apos;s booked. Approve
            follow-ups with one tap. Send a voice note and Ondra turns it into tasks for your team.
          </p>
          <p className="mt-4 max-w-[50ch] text-[16px] leading-relaxed text-muted">
            When you want the full picture, the web dashboard has revenue, the inbox, the calendar, client profiles and
            the task board.
          </p>
        </div>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- guardrails */

function Guardrails() {
  const items = [
    {
      t: "Approve first",
      p: "For the first week, every reply the AI writes waits for your approval. Switch on automatic replies when you trust them.",
    },
    {
      t: "No promises you didn't make",
      p: "It won't commit to a final price, a discount or a delivery date unless your policy says it can.",
    },
    {
      t: "Hands off when it should",
      p: "If it isn't sure, or a buyer is upset, it passes the conversation to a person with a brief and alerts a manager if needed.",
    },
    {
      t: "STOP means stop",
      p: "When a customer opts out, Ondra stops messaging them on every channel, straight away.",
    },
    {
      t: "Learns your answers",
      p: "Questions it couldn't answer land in one list. Answer once and it uses your answer from then on.",
    },
    {
      t: "Your data stays yours",
      p: "Each dealer's data is kept separate and encrypted, and is never used to train AI models.",
    },
  ];
  return (
    <section className="bg-paper py-24 sm:py-32">
      <Wrap>
        <p className="eyebrow text-muted">Control</p>
        <H2 className="mt-3 max-w-[18ch]">The AI works for you. You stay in charge.</H2>
        <ul className="mt-12 grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((i) => (
            <li key={i.t} className="border-t-2 border-ink pt-5">
              <b className="x block text-[20px]">{i.t}</b>
              <p className="mt-2.5 text-[16px] leading-relaxed text-ink-2">{i.p}</p>
            </li>
          ))}
        </ul>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- setup */

function Setup() {
  const steps = [
    {
      t: "Connect your channels",
      p: "Forward your phone line and your sales and service email. Connect your WhatsApp Business number through Meta. Customers keep using the details they already have.",
    },
    {
      t: "Show the agents how you work",
      p: "Your hours, your inventory, what can be booked, who handles what, and which clients are VIPs who always reach you.",
    },
    {
      t: "Approve, then let go",
      p: "Watch the first week in draft mode and correct anything that's off. Turn on automatic replies channel by channel.",
    },
  ];
  return (
    <section className="bg-ink py-24 text-white sm:py-32">
      <Wrap>
        <p className="eyebrow text-sodium">Getting started</p>
        <H2 className="mt-3 max-w-[18ch]">Staff the desks without hiring.</H2>
        <p className="mt-5 max-w-[60ch] text-[18px] leading-relaxed text-[#C9CBD1]">
          Phone and email can be answered within days. WhatsApp goes live once Meta approves your business account,
          and we walk you through that.
        </p>
        <ol className="mt-12 grid gap-10 md:grid-cols-3">
          {steps.map((s, i) => (
            <li key={s.t} className="border-t border-white/25 pt-5">
              <span className="x text-[15px] font-bold text-sodium">0{i + 1}</span>
              <b className="x mt-1 block text-[21px]">{s.t}</b>
              <p className="mt-2.5 text-[16px] leading-relaxed text-[#C9CBD1]">{s.p}</p>
            </li>
          ))}
        </ol>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- fit */

function Fit() {
  const fits = [
    { t: "Independent and franchised dealers", p: "Across the US, with or without a DMS." },
    { t: "Exporters", p: "Selling to buyers in Africa and the Middle East, mostly over WhatsApp." },
    { t: "Community dealers", p: "Serving immigrant communities whose buyers would rather message than call." },
  ];
  return (
    <section className="bg-paper py-24 sm:py-32">
      <Wrap>
        <H2 className="max-w-[20ch]">Made for dealers whose buyers won&apos;t wait for Monday.</H2>
        <ul className="mt-12 grid gap-4 md:grid-cols-3">
          {fits.map((f) => (
            <li key={f.t} className="rounded-xl border border-line bg-white p-6">
              <b className="x block text-[20px] leading-tight">{f.t}</b>
              <p className="mt-2.5 text-[15.5px] leading-relaxed text-ink-2">{f.p}</p>
            </li>
          ))}
        </ul>
        <p className="mt-8 max-w-[64ch] text-[16px] leading-relaxed text-muted">
          We&apos;re building Ondra with an independent luxury dealer in Dallas who exports to Nigeria, and taking on a
          small number of pilot dealers alongside them.
        </p>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- demo */

function Demo() {
  return (
    <section id="demo" className="scroll-mt-4 border-t border-line bg-paper-2 py-24 sm:py-32">
      <Wrap className="grid gap-12 lg:grid-cols-[1fr_1.25fr]">
        <div>
          <p className="eyebrow text-muted">Book a demo</p>
          <H2 className="mt-3 max-w-[14ch]">See it answer your buyers.</H2>
          <p className="mt-5 max-w-[44ch] text-[18px] leading-relaxed text-ink-2">
            Tell us how buyers reach you today. On the call we&apos;ll look at where leads slip through, then show Ondra
            answering the kinds of questions you get, on WhatsApp and on the phone.
          </p>
          <ul className="mt-8 space-y-3 text-[16px] text-ink-2">
            <li className="flex gap-3">
              <span className="text-sodium">●</span> Pilot places are limited while we onboard dealers one by one.
            </li>
            <li className="flex gap-3">
              <span className="text-sodium">●</span> Prefer WhatsApp? Leave your number and we&apos;ll message you there.
            </li>
          </ul>
        </div>
        <DemoForm />
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- FAQ */

function Faq() {
  const qs = [
    {
      q: "Do my customers get a new phone number or WhatsApp?",
      a: "No. You keep your number, WhatsApp and email. Calls reach Ondra through call forwarding, either for every call or only when your team doesn't pick up. WhatsApp connects through Meta's official API, and email through forwarding or by connecting Gmail or Microsoft 365.",
    },
    {
      q: "What happens when the AI doesn't know the answer?",
      a: "It tells the customer someone will follow up, hands the conversation to the right person with a short brief, and adds the question to your unanswered list. Answer it once and the AI knows it from then on.",
    },
    {
      q: "Can it give prices or discounts?",
      a: "Only what your policy allows. By default it won't commit to a final price, a discount or a delivery date. It passes those to your team.",
    },
    {
      q: "We don't use a DMS. Will it work?",
      a: "Yes. Ondra keeps client profiles, deals, tasks and the calendar itself. If you do use a DMS or CRM, tell us which one and we'll talk about connecting it.",
    },
    {
      q: "Can my staff keep using the WhatsApp Business app?",
      a: "In most cases, yes. Where Meta supports it, your team keeps using the app on the same number while Ondra works alongside it. We'll confirm this for your number during setup.",
    },
    {
      q: "Are calls recorded?",
      a: "Calls are recorded and transcribed so your team can review them. Ondra plays a recording notice at the start of the call in states that require it.",
    },
    {
      q: "How much does it cost?",
      a: "Pricing is being set with our pilot dealers. We'll go through it on the demo call, based on your size and channels.",
    },
  ];
  return (
    <section id="faq" className="scroll-mt-4 bg-paper py-24 sm:py-32">
      <Wrap className="grid gap-12 lg:grid-cols-[1fr_2fr]">
        <H2>Questions dealers ask.</H2>
        <div className="divide-y divide-line border-y border-line">
          {qs.map((i) => (
            <details key={i.q} className="group py-5">
              <summary className="flex cursor-pointer list-none items-start justify-between gap-6 text-[18px] font-semibold [&::-webkit-details-marker]:hidden">
                {i.q}
                <span aria-hidden="true" className="mt-0.5 text-2xl leading-none text-muted transition group-open:rotate-45">
                  +
                </span>
              </summary>
              <p className="mt-3 max-w-[65ch] text-[16px] leading-relaxed text-ink-2">{i.a}</p>
            </details>
          ))}
        </div>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- footer */

function Footer() {
  return (
    <footer className="bg-ink py-12 text-[#B9BBC2]">
      <Wrap className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <Logo className="text-white" />
          <p className="mt-3 max-w-[40ch] text-sm">AI agents that answer, book and route for car dealerships.</p>
        </div>
        <div className="text-sm">
          <a href={`mailto:${CONTACT_EMAIL}`} className="underline-offset-4 hover:underline">
            {CONTACT_EMAIL}
          </a>
          <p className="mt-1">© {new Date().getFullYear()} Ondra (working name)</p>
        </div>
      </Wrap>
    </footer>
  );
}
