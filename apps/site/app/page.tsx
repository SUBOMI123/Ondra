import {
  IconArrowForwardUp,
  IconBrandWhatsapp,
  IconCalendarEvent,
  IconCheck,
  IconMail,
  IconMessage,
  IconPhone,
  IconPlus,
  IconSparkles,
} from "@tabler/icons-react";
import DemoForm from "@/components/DemoForm";
import Appear from "@/components/Appear";
import ChannelFlow from "@/components/ChannelFlow";
import FloorTour from "@/components/FloorTour";
import HeroTitle from "@/components/HeroTitle";
import Wordmark from "@/components/Wordmark";
import MobileMenu from "@/components/MobileMenu";
import { NAV_LINKS } from "@/components/navLinks";
import { Briefing, PolicyCheck, SalesThread, ServiceCall, VipCall } from "@/components/stories";
import StickyNav from "@/components/StickyNav";
import { VipTag } from "@/components/vip";
import { CONTACT_EMAIL, SIGN_IN_URL } from "@/lib/config";

export default function Home() {
  return (
    <>
      <Nav />
      <StickyNav />
      <main>
        <Hero />
        {/* The walk continues the hero's "fully staffed" line, so it comes straight after it. */}
        <div id="tour">
          <FloorTour />
        </div>
        <Night />
        <ChannelFlow />
        <Inbox />
        <Sales />
        <Service />
        <Vip />
        <MorningBriefing />
        <Guardrails />
        <Setup />
        <Demo />
        <Faq />
      </main>
      <Footer />
    </>
  );
}

/* ---------------------------------------------------------------- primitives */

function Wrap({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-(--container-page) px-4 sm:px-7 ${className}`}>{children}</div>;
}

function H2({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <h2 className={`font-display text-h2 ${className}`}>{children}</h2>;
}

function Lead({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <p className={`text-lead max-w-(--container-prose) ${className}`}>{children}</p>;
}

function Logo({ className = "" }: { className?: string }) {
  return (
    <a href="#top" className={`flex items-center no-underline ${className}`}>
      <Wordmark className="h-[23px] w-auto" />
    </a>
  );
}

const CHANNELS = [
  { name: "Phone", Icon: IconPhone },
  { name: "Text", Icon: IconMessage },
  { name: "Email", Icon: IconMail },
  { name: "WhatsApp", Icon: IconBrandWhatsapp },
] as const;

/* ---------------------------------------------------------------- nav */

function Nav() {
  return (
    <header className="on-dark absolute inset-x-0 top-0 z-30">
      <Wrap className="flex items-center justify-between py-5 text-white">
        <Logo />
        <nav aria-label="Main" className="flex items-center gap-7 text-[15px]">
          {NAV_LINKS.map(([label, href]) => (
            <a key={href} href={href} className="hidden text-white/80 no-underline hover:text-white md:inline">
              {label}
            </a>
          ))}
          <a href={SIGN_IN_URL} className="hidden text-white/80 no-underline hover:text-white sm:inline md:border-l md:border-white/15 md:pl-7">
            Sign in
          </a>
          <a href="#demo" className="btn btn-primary min-h-11 px-4">
            Book a demo
          </a>
          <div data-menu="main" className="-mr-2 md:hidden">
            <MobileMenu />
          </div>
        </nav>
      </Wrap>
    </header>
  );
}

/* ---------------------------------------------------------------- hero */

function Hero() {
  return (
    <section id="top" className="relative isolate flex min-h-[min(940px,100svh)] flex-col overflow-hidden bg-night text-fg">
      {/* The first frame of the 3D walk under a night sky, so the hero flows straight into the floor tour below. */}
      <picture>
        <source media="(max-aspect-ratio: 6/5)" srcSet="/walk-portrait/frame_0001.jpg" />
        <img
          src="/walk/frame_0001.jpg"
          width={1600}
          height={900}
          alt=""
          fetchPriority="high"
          className="absolute inset-0 -z-20 size-full object-cover object-bottom opacity-55 motion-safe:animate-settle"
        />
      </picture>
      {/* Night above, a warm sodium glow rising off the polished floor */}
      <div aria-hidden="true" className="absolute inset-0 -z-10 bg-[linear-gradient(180deg,var(--color-night)_0%,rgb(11_9_7/0.72)_38%,rgb(11_9_7/0.25)_68%,var(--color-night)_100%)]" />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 -z-10 h-[70%] bg-[radial-gradient(70%_55%_at_50%_100%,rgb(242_163_58/0.22),transparent_70%)]" />

      <Wrap className="flex flex-1 flex-col items-center justify-center pb-12 pt-40 text-center sm:pb-16">
        <HeroTitle text="Your dealership, fully staffed." className="font-display text-display max-w-[14ch] text-balance" />
        <p className="text-lead mt-7 max-w-[46ch] text-fg-2 motion-safe:animate-rise [animation-delay:600ms]">
          Ondra answers every call, text and email in seconds, day or night, books the appointment, and hands the deal to
          the right person on your team.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-3 motion-safe:animate-rise [animation-delay:750ms]">
          <a href="#demo" className="btn btn-primary">
            Book a demo
          </a>
          <a href="#tour" className="btn btn-quiet">
            Walk the floor
          </a>
        </div>
      </Wrap>

      <Wrap className="pb-8">
        <div className="flex flex-col items-center gap-4 border-t border-line pt-6 sm:flex-row sm:justify-between">
          <p className="text-small text-muted-foreground">Keeps your phone numbers and email addresses.</p>
          <ul aria-label="Channels" className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-small text-fg-2">
            {CHANNELS.map(({ name, Icon }) => (
              <li key={name} className="flex items-center gap-2">
                <Icon size={16} stroke={1.5} aria-hidden="true" />
                {name}
              </li>
            ))}
          </ul>
        </div>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- inbox (the product) */

type Row = {
  name: string;
  place: string;
  Icon: typeof IconPhone;
  time: string;
  snippet: string;
  tag: { kind: "ai" | "draft" | "vip" | "team"; text: string };
  vip?: boolean;
  selected?: boolean;
};

const ROWS: Row[] = [
  { name: "Kevin L.", place: "Allen", Icon: IconMail, time: "9:12 pm", snippet: "6 works. See you Thursday.", tag: { kind: "ai", text: "Booked by Ondra" }, selected: true },
  { name: "Robert H.", place: "Highland Park", Icon: IconPhone, time: "8:52 pm", snippet: "Missed call. Rang Daniel.", tag: { kind: "vip", text: "Waiting 2 h" }, vip: true },
  { name: "Sarah K.", place: "Dallas", Icon: IconMessage, time: "8:40 pm", snippet: "Do you take trade-ins on a 2019 Tahoe?", tag: { kind: "draft", text: "Draft waiting for you" } },
  { name: "Marcus T.", place: "Plano", Icon: IconPhone, time: "7:05 pm", snippet: "Brakes squeaking, booked Wednesday.", tag: { kind: "ai", text: "Booked by Ondra" } },
  { name: "Elena R.", place: "Frisco", Icon: IconBrandWhatsapp, time: "6:30 pm", snippet: "Is the 2020 RX certified pre-owned?", tag: { kind: "team", text: "With Daniel, Sales" } },
];

function Tag({ kind, text }: Row["tag"]) {
  const cls = {
    ai: "bg-ai-subtle text-ai",
    draft: "border border-dashed border-ai/40 text-ai",
    vip: "bg-vip-subtle text-vip",
    team: "bg-muted text-fg-2",
  }[kind];
  return (
    <span className={`text-micro inline-flex items-center gap-1 rounded-pill px-2 py-0.5 font-medium ${cls}`}>
      {kind === "vip" || kind === "team" ? null : <IconSparkles size={12} stroke={2} aria-hidden="true" />}
      {text}
    </span>
  );
}

function AiMessage({ children, meta }: { children: React.ReactNode; meta: string }) {
  return (
    <div data-slot="ai-bubble" className="ml-auto max-w-[78%]">
      <div className="rounded-card rounded-tr-sm border border-ai/15 bg-ai-subtle px-4 py-3 text-fg">{children}</div>
      <p className="text-micro mt-1.5 flex items-center justify-end gap-1 text-ai">
        <IconSparkles size={12} stroke={2} aria-hidden="true" />
        <span className="font-medium">Sent by Ondra</span>
        <span className="text-muted-foreground">{meta}</span>
      </p>
    </div>
  );
}

function BuyerMessage({ children, meta }: { children: React.ReactNode; meta: string }) {
  return (
    <div className="max-w-[78%]">
      <div className="rounded-card rounded-tl-sm bg-bg px-4 py-3">{children}</div>
      <p className="text-micro mt-1.5 text-muted-foreground">{meta}</p>
    </div>
  );
}

function Inbox() {
  return (
    <section id="how" className="scroll-mt-14 bg-bg py-24 sm:py-32 border-t border-line">
      <div className="mx-auto w-full max-w-(--container-page) px-4 sm:px-7">
        <div className="grid gap-6 lg:grid-cols-2 lg:items-end">
          <h2 className="font-display text-h2 max-w-[15ch]">All your conversations in one inbox.</h2>
          <p className="text-lead max-w-(--container-prose) text-fg-2">
            Calls, texts, email and WhatsApp, side by side. Anything Ondra said, drafted or booked is marked in blue with its
            name on it, so you always know what came from the AI.
          </p>
        </div>

        <figure className="mt-14">
          <div aria-hidden="true" className="overflow-hidden rounded-panel bg-surface shadow-panel ring-1 ring-white/8">
            <div className="grid md:grid-cols-[minmax(0,21rem)_minmax(0,1fr)]">
              {/* Conversation list */}
              <div className="hidden border-r border-line md:block">
                <div className="flex items-center justify-between border-b border-line px-5 py-4">
                  <p className="font-display text-h4">Inbox</p>
                  <div className="text-micro flex gap-1.5">
                    <span className="rounded-pill bg-night px-2.5 py-1 text-white">All</span>
                    <span className="rounded-pill bg-muted px-2.5 py-1 text-fg">Needs you 1</span>
                    <span className="rounded-pill bg-muted px-2.5 py-1">Drafts 1</span>
                  </div>
                </div>
                <ul>
                  {ROWS.map((r) => (
                    <li
                      key={r.name}
                      data-vip={r.vip || undefined}
                      className={`relative border-b border-line px-5 py-4 ${r.selected ? "bg-accent before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-brand" : ""}`}
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <p className="flex items-center gap-1.5 font-semibold">
                          {r.vip && <VipTag />}
                          {r.name}
                          <span className="text-small font-normal text-muted-foreground">{r.place}</span>
                        </p>
                        <span className="text-micro shrink-0 tabular-nums text-muted-foreground">{r.time}</span>
                      </div>
                      <p className="text-small mt-1 flex items-center gap-1.5 truncate text-fg-2">
                        <r.Icon size={15} stroke={1.75} className="shrink-0 text-muted-foreground" aria-hidden="true" />
                        <span className="truncate">{r.snippet}</span>
                      </p>
                      <div className="mt-2">
                        <Tag {...r.tag} />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Thread */}
              <div className="flex min-w-0 flex-col">
                <div className="border-b border-line px-5 py-4 sm:px-7">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <span className="flex size-9 items-center justify-center rounded-full bg-muted text-fg-2">
                        <IconMail size={18} stroke={1.75} />
                      </span>
                      <div>
                        <p className="font-semibold">Kevin L.</p>
                        <p className="text-micro text-muted-foreground">Email, from your website</p>
                      </div>
                    </div>
                    <p className="text-micro tabular-nums">
                      <span className="text-muted-foreground">Received </span>9:12 pm
                      <span className="text-muted-foreground">, showroom closed</span>
                    </p>
                  </div>
                  <dl className="text-micro mt-4 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-5">
                    {[
                      ["Vehicle", "2022 Silverado LT"],
                      ["Budget", "About $45k"],
                      ["Financing", "Needs it"],
                      ["Trade-in", "None"],
                      ["Timeline", "This week"],
                    ].map(([k, v]) => (
                      <div key={k}>
                        <dt className="text-muted-foreground">{k}</dt>
                        <dd className="text-small font-medium">{v}</dd>
                      </div>
                    ))}
                  </dl>
                  <p className="text-micro mt-3 flex items-center gap-1 text-ai">
                    <IconSparkles size={12} stroke={2} />
                    Profile filled in by Ondra from the conversation
                  </p>
                </div>

                <div className="text-small flex flex-1 flex-col gap-4 bg-canvas px-5 py-6 sm:px-7">
                  <Appear delay={0}>
                    <BuyerMessage meta="9:12 pm">Is the gray 2022 Silverado still available? Is the price negotiable? I&apos;d need financing.</BuyerMessage>
                  </Appear>

                  <Appear delay={0.5}>
                    <AiMessage meta="9:12 pm">
                    It&apos;s here: Silverado LT, 28k miles. Daniel can go through price and financing with you in person.
                    Could you come by Thursday after work, say 6 pm?
                  </AiMessage>
                  </Appear>

                  <Appear delay={1.1}>
                    <BuyerMessage meta="9:20 pm">6 works. See you Thursday.</BuyerMessage>
                  </Appear>

                  <Appear delay={1.6}>
                    <AiMessage meta="9:20 pm">Booked. The truck will be pulled up front, and Daniel can start your credit application before you arrive if you like.</AiMessage>
                  </Appear>

                  <Appear delay={2.1}>
                    <div className="flex items-center gap-3 text-ai">
                    <span className="h-px flex-1 bg-ai/15" />
                    <span className="text-micro flex items-center gap-1.5 font-medium">
                      <IconCalendarEvent size={14} stroke={1.75} />
                      Test drive booked by Ondra for Thursday, 6:00 pm
                    </span>
                    <span className="h-px flex-1 bg-ai/15" />
                  </div>
                  </Appear>

                  <Appear delay={2.6}>
                  <div className="rounded-card border border-line bg-surface p-4">
                    <p className="flex items-center gap-2 font-semibold">
                      <IconArrowForwardUp size={16} stroke={1.75} className="text-muted-foreground" />
                      Ondra passed this to Daniel, Sales
                    </p>
                    <blockquote className="mt-2 border-l-2 border-line pl-3 text-fg-2">
                      Wants the Silverado, asked if the price is negotiable. I didn&apos;t quote. Needs financing, no trade.
                      Worth a call to pre-qualify before Thursday.
                    </blockquote>
                    <div className="text-micro mt-3 flex flex-wrap gap-2">
                      <span className="rounded-pill bg-muted px-2.5 py-1">Due Thursday, noon</span>
                      <span className="rounded-pill bg-muted px-2.5 py-1">Daniel accepted</span>
                    </div>
                  </div>
                  </Appear>
                </div>

                <div className="flex items-center gap-3 border-t border-line px-5 py-3.5 sm:px-7">
                  <span className="text-small flex-1 rounded-control border border-line px-3.5 py-2.5 text-muted-foreground">Reply as Daniel</span>
                  <span className="btn btn-primary min-h-10 px-4 text-sm">Send</span>
                </div>
              </div>
            </div>
          </div>
          <figcaption className="text-small mt-4 text-muted-foreground">Example conversation. Names and details are illustrative.</figcaption>
        </figure>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- the night */

function Night() {
  const hours = [
    {
      t: "7:40 pm",
      p: "A buyer calls about the Silverado. The showroom closed at seven, so he calls the next dealer on his list.",
    },
    {
      t: "9:12 pm",
      p: "A lead from your website lands in a shared inbox nobody checks after six.",
    },
    {
      t: "11:15 pm",
      p: "Two texts land on Daniel's personal phone. He's asleep, and nobody else can see them.",
    },
    {
      t: "9:00 am",
      p: "You open up. Nothing tells you what you missed.",
    },
  ];
  return (
    <section className="border-t border-line bg-bg-2 py-24 sm:py-32">
      <Wrap className="grid gap-12 lg:grid-cols-[1fr_1.4fr]">
        <div>
          <H2 className="max-w-[14ch]">One night with nobody on the phones.</H2>
          <Lead className="mt-5 text-fg-2">Buyers call and message after you close. Most of those go nowhere.</Lead>
        </div>
        <ol className="border-l border-fg/15">
          {hours.map((h, i) => (
            <li key={h.t} className="relative grid gap-1 pb-10 pl-8 last:pb-0 sm:grid-cols-[9.5rem_1fr] sm:gap-6">
              <span aria-hidden="true" className={`absolute -left-[5px] top-2.5 size-[9px] rounded-full ${i === hours.length - 1 ? "bg-night" : "bg-bg-2 ring-2 ring-fg/40"}`} />
              <p className="font-display text-h3 whitespace-nowrap tabular-nums">{h.t}</p>
              <p className="max-w-[46ch] pt-1 text-fg-2">{h.p}</p>
            </li>
          ))}
        </ol>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- sales */

function Points({ items }: { items: string[][] }) {
  return (
    <dl className="mt-10 grid gap-5">
      {items.map(([t, d]) => (
        <div key={t} className="grid gap-1 sm:grid-cols-[12rem_1fr] sm:gap-6">
          <dt className="font-medium">{t}</dt>
          <dd className="text-fg-2">{d}</dd>
        </div>
      ))}
    </dl>
  );
}

function Sales() {
  return (
    <section id="sales" className="scroll-mt-14 border-t border-line bg-night py-24 sm:py-32">
      <Wrap className="grid items-center gap-16 lg:grid-cols-[1.05fr_1fr]">
        <div>
          <H2 className="max-w-[15ch]">Every lead answered while it&apos;s still warm.</H2>
          <Lead className="mt-5 text-fg-2">
            Ondra knows your lot. It answers the question, suggests the right cars from your stock, books the test drive and
            hands your salesperson a buyer who&apos;s ready.
          </Lead>
          <Points
            items={[
              ["Knows your inventory", "Real stock, mileage and listed prices from your feed or DMS, so it only talks about cars you have."],
              ["Captures the deal", "Budget, trade-in, financing and timeline go straight into the client profile."],
              ["No DMS? No problem", "Ondra keeps clients, deals and tasks itself. Have a DMS? We'll connect it."],
            ]}
          />
        </div>
        <SalesThread />
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- service */

function Service() {
  return (
    <section id="service" className="scroll-mt-14 border-t border-line bg-bg-2 py-24 sm:py-32">
      <Wrap className="grid items-center gap-16 lg:grid-cols-[1fr_1.05fr]">
        <div className="order-2 lg:order-1">
          <ServiceCall />
        </div>
        <div className="order-1 lg:order-2">
          <H2 className="max-w-[16ch]">Service calls, picked up on the first ring.</H2>
          <Lead className="mt-5 text-fg-2">
            Ondra answers the call, finds the customer and their vehicle, books a bay that&apos;s actually free and tells the
            advisor why they&apos;re coming.
          </Lead>
          <Points
            items={[
              ["Books real capacity", "Your bays, advisors and appointment lengths. No double-booking."],
              ["Reminders that land", "Confirmations and reminders by text, with reschedules handled in the thread."],
              ["Knows when to hand off", "An upset customer or a warranty question goes to your advisor with a brief."],
            ]}
          />
        </div>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- VIP */

function Vip() {
  return (
    <section id="vip" className="scroll-mt-14 border-t border-line bg-bg py-24 sm:py-32">
      <Wrap className="grid items-center gap-16 lg:grid-cols-2">
        <div>
          <H2 className="max-w-[15ch]">Some clients should only ever hear from you.</H2>
          <Lead className="mt-5 text-fg-2">
            Mark a client, or the people who buy for them, as VIP, and choose who looks after them. Their calls ring that person
            directly and their messages wait for a personal reply. The AI never answers them or writes a reply for them.
          </Lead>
          <p className="mt-4 max-w-[50ch] text-muted-foreground">Miss the call and they get an alert straight away, not a summary at the end of the day. The caller hears your own words, never the AI.</p>
        </div>
        <VipCall />
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- morning briefing */

function MorningBriefing() {
  return (
    <section className="border-t border-line bg-bg-2 py-24 sm:py-32">
      <Wrap className="grid items-center gap-16 lg:grid-cols-[1fr_1.05fr]">
        <div className="order-2 lg:order-1">
          <Briefing />
        </div>
        <div className="order-1 lg:order-2">
          <H2 className="max-w-[15ch]">Run your morning from your phone.</H2>
          <Lead className="mt-5 text-fg-2">
            A WhatsApp briefing before you get to the lot: who&apos;s waiting, what came in overnight, what&apos;s booked. Approve
            follow-ups with one tap. Send a voice note and Ondra turns it into tasks for your team.
          </Lead>
          <p className="mt-4 max-w-[50ch] text-muted-foreground">
            The web dashboard has the full picture: revenue, the inbox, the calendar, client profiles and the task board.
          </p>
        </div>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- guardrails */

function Guardrails() {
  const items = [
    ["Approve first", "For the first week, every reply waits for your approval."],
    ["Hands off when it should", "Unsure, or a buyer is upset? It passes to a person with a brief."],
    ["STOP means stop", "Opt-outs stop messages on every channel, straight away."],
    ["Learns your answers", "Questions it couldn't answer land in one list. Answer once."],
    ["Your data stays yours", "Kept separate, encrypted, never used to train AI models."],
  ];
  return (
    <section className="border-t border-line bg-bg py-24 sm:py-32">
      <Wrap>
        <div className="grid gap-6 lg:grid-cols-2 lg:items-end">
          <H2 className="max-w-[16ch]">Prices and dates stay with your team.</H2>
          <Lead className="text-fg-2">
            Every reply is checked against your rules before it goes out. Ondra won&apos;t commit to a final price, a discount
            or a delivery date unless you&apos;ve said it can.
          </Lead>
        </div>
        <div className="mt-14 grid gap-10 lg:grid-cols-[1.3fr_1fr] lg:items-start">
          <PolicyCheck />
          <dl className="divide-y divide-line border-y border-line">
            {items.map(([t, d]) => (
              <div key={t} className="py-4">
                <dt className="font-medium">{t}</dt>
                <dd className="text-small mt-1 text-muted-foreground">{d}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- setup */

function Setup() {
  const steps = [
    ["Connect your channels", "Forward your sales and service lines and email. Add WhatsApp if your customers use it. Customers keep the numbers and addresses they already have."],
    ["Show the agents how you work", "Your hours, your stock, what can be booked, who handles what, and which clients are VIPs who always reach you."],
    ["Approve, then let go", "Watch the first week in draft mode and correct anything that's off. Turn on automatic replies channel by channel."],
  ];
  return (
    <section className="on-dark bg-night py-24 text-white sm:py-32 border-t border-line">
      <Wrap>
        <H2 className="max-w-[18ch]">Up and running in a few days.</H2>
        <Lead className="mt-5 text-white/70">
          Phone and email can be answered within days. Business texting and WhatsApp need carrier and Meta registration,
          which takes a few weeks. We do the paperwork with you.
        </Lead>
        <ol className="mt-14 grid gap-10 md:grid-cols-3">
          {steps.map(([t, p], i) => (
            <li key={t} className="border-t border-white/20 pt-5">
              <span className="font-display text-h3 text-brand-text tabular-nums">{i + 1}</span>
              <p className="font-display text-h4 mt-2">{t}</p>
              <p className="mt-2.5 text-white/70">{p}</p>
            </li>
          ))}
        </ol>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- demo */

function Demo() {
  return (
    <section id="demo" className="scroll-mt-4 border-t border-line bg-bg-2 py-24 sm:py-32">
      <Wrap className="grid gap-12 lg:grid-cols-[1fr_1.25fr]">
        <div>
          <H2 className="max-w-[12ch]">See it answer your buyers.</H2>
          <Lead className="mt-5 text-fg-2">
            Tell us how buyers reach you today. On the call we&apos;ll look at where leads slip through, then show Ondra
            answering the kinds of questions you get, on the phone and by text.
          </Lead>
          <div className="mt-10 border-t border-line pt-6">
            <p className="font-semibold">Who we&apos;re piloting with</p>
            <ul className="mt-3 space-y-3 text-fg-2">
              {[
                ["Independent dealers", "with or without a DMS"],
                ["Franchised stores", "that want sales and service covered after hours"],
                ["Dealers whose buyers would rather message", "than call, by text or WhatsApp"],
              ].map(([t, d]) => (
                <li key={t} className="flex gap-3">
                  <IconCheck size={20} stroke={1.75} className="mt-0.5 shrink-0 text-ok" aria-hidden="true" />
                  <span>
                    <b className="font-semibold text-fg">{t}</b> {d}
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-small mt-5 text-muted-foreground">
              We&apos;re building Ondra with an independent luxury dealer in Dallas. Pilot places
              are limited while we onboard dealers one by one.
            </p>
          </div>
        </div>
        <DemoForm />
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- FAQ */

function Faq() {
  const qs = [
    ["Do my customers get a new phone number?", "No. You keep your numbers, email addresses and WhatsApp. Calls reach Ondra through call forwarding, either for every call or only when your team doesn't pick up. WhatsApp connects through Meta's official API, and email through forwarding or by connecting Gmail or Microsoft 365."],
    ["What happens when the AI doesn't know the answer?", "It tells the customer someone will follow up, hands the conversation to the right person with a short brief, and adds the question to your unanswered list. Answer it once and the AI knows it from then on."],
    ["Can it give prices or discounts?", "Only what your policy allows. By default it won't commit to a final price, a discount or a delivery date. It passes those to your team."],
    ["We don't use a DMS. Will it work?", "Yes. Ondra keeps client profiles, deals, tasks and the calendar itself. If you do use a DMS or CRM, tell us which one and we'll talk about connecting it."],
    ["Can my staff keep using the WhatsApp Business app?", "In most cases, yes. Where Meta supports it, your team keeps using the app on the same number while Ondra works alongside it. We'll confirm this for your number during setup."],
    ["Are calls recorded?", "Calls are recorded and transcribed so your team can review them. Ondra plays a recording notice at the start of the call in states that require it."],
    ["How much does it cost?", "Pricing is being set with our pilot dealers. We'll go through it on the demo call, based on your size and channels."],
  ];
  return (
    <section id="faq" className="scroll-mt-4 bg-bg py-24 sm:py-32 border-t border-line">
      <Wrap className="grid gap-12 lg:grid-cols-[1fr_2fr]">
        <H2>Questions dealers ask.</H2>
        <div className="divide-y divide-line border-y border-line">
          {qs.map(([q, a]) => (
            <details key={q} className="group py-5">
              <summary className="flex cursor-pointer list-none items-start justify-between gap-6 text-[18px] font-semibold [&::-webkit-details-marker]:hidden">
                {q}
                <IconPlus size={22} stroke={1.5} aria-hidden="true" className="mt-0.5 shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-45" />
              </summary>
              <p className="mt-3 max-w-[65ch] text-fg-2">{a}</p>
            </details>
          ))}
        </div>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- footer */

function Footer() {
  const col = "flex flex-col gap-2.5";
  const link = "w-fit text-white/65 no-underline hover:text-white";
  return (
    <footer className="on-dark bg-night text-white/65">
      <Wrap className="grid grid-cols-2 gap-x-8 gap-y-12 py-16 md:grid-cols-[minmax(0,1.4fr)_repeat(2,minmax(0,1fr))]">
        <div className="col-span-2 flex flex-col items-start gap-5 md:col-span-1">
          <Logo className="text-white" />
          <p className="text-small max-w-[34ch]">AI staff for car dealerships: answers every call, text, WhatsApp and email, books the test drive, and hands the rest to your team.</p>
          <a href="#demo" className="btn btn-primary min-h-11 px-4">Book a demo</a>
        </div>
        <nav aria-label="Product" className={col}>
          <p className="text-small font-medium text-white">Product</p>
          {NAV_LINKS.map(([label, href]) => (
            <a key={href} href={href} className={`text-small ${link}`}>{label}</a>
          ))}
        </nav>
        <nav aria-label="Company" className={col}>
          <p className="text-small font-medium text-white">Company</p>
          <a href={SIGN_IN_URL} className={`text-small ${link}`}>Sign in</a>
          <a href="#demo" className={`text-small ${link}`}>Book a demo</a>
          <a href={`mailto:${CONTACT_EMAIL}`} className={`text-small ${link}`}>{CONTACT_EMAIL}</a>
        </nav>
      </Wrap>
      <div className="border-t border-white/10">
        <Wrap className="flex flex-col gap-3 py-6 sm:flex-row sm:items-start sm:justify-between">
          <p className="text-micro shrink-0">© {new Date().getFullYear()} Ondra</p>
          {/* The licences require these credits (design/3d/README.md). */}
          <p className="text-micro max-w-[80ch] text-white/40 sm:text-right">
            3D car models from Blend Swap: Audi A8 by 50Groszy (CC BY-SA 3.0), BMW M4 F82 (#81957, CC BY 3.0), Lamborghini Urus
            2019 (#92440, CC BY-NC 3.0), 1968 Mustang GT Fastback (#82339, CC0). Badges and logos removed, paint changed.
          </p>
        </Wrap>
      </div>
    </footer>
  );
}
