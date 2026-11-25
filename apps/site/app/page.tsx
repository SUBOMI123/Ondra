import {
  IconArrowForwardUp,
  IconBrandInstagram,
  IconBrandWhatsapp,
  IconCalendarEvent,
  IconCheck,
  IconCrownFilled,
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
import StickyNav from "@/components/StickyNav";
import { CONTACT_EMAIL } from "@/lib/config";

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
        <WhatsApp />
        <Vip />
        <OwnerBriefing />
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
    <a href="#top" className={`font-display flex items-center gap-2.5 text-xl font-bold no-underline ${className}`}>
      <i aria-hidden="true" className="block size-[11px] rounded-full bg-brand" />
      Ondra
    </a>
  );
}

const CHANNELS = [
  { name: "Phone", Icon: IconPhone },
  { name: "WhatsApp", Icon: IconBrandWhatsapp },
  { name: "SMS", Icon: IconMessage },
  { name: "Email", Icon: IconMail },
] as const;

/* ---------------------------------------------------------------- nav */

function Nav() {
  return (
    <header className="on-dark absolute inset-x-0 top-0 z-30">
      <Wrap className="flex items-center justify-between py-5 text-white">
        <Logo />
        <nav aria-label="Main" className="flex items-center gap-7 text-[15px]">
          {[
            ["How it works", "#how"],
            ["WhatsApp", "#whatsapp"],
            ["VIPs", "#vip"],
            ["FAQ", "#faq"],
          ].map(([label, href]) => (
            <a key={href} href={href} className="hidden text-white/80 no-underline hover:text-white md:inline">
              {label}
            </a>
          ))}
          <a href="#demo" className="btn btn-primary min-h-11 px-4">
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
      {/* Twilight: deep navy at the top fading into the lit floor, then night at the foot */}
      <div aria-hidden="true" className="absolute inset-0 -z-10 bg-linear-to-b from-twilight via-twilight/60 to-night" />
      <div aria-hidden="true" className="absolute inset-x-0 top-0 -z-10 h-2/3 bg-linear-to-b from-dusk/25 to-transparent" />

      <Wrap className="flex flex-1 flex-col items-center justify-center pb-12 pt-40 text-center sm:pb-16">
        <HeroTitle text="Your dealership, fully staffed." className="font-display text-display max-w-[14ch] text-balance" />
        <p className="text-lead mt-7 max-w-[46ch] text-fg-2 motion-safe:animate-rise [animation-delay:600ms]">
          Ondra answers every call, WhatsApp, text and email in seconds, day or night, then hands the deal to the right
          person on your team.
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
          <p className="text-small text-muted-foreground">Keeps your number, WhatsApp and email.</p>
          <ul aria-label="Channels" className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-small text-fg-2">
            {CHANNELS.map(({ name, Icon }) => (
              <li key={name} className="flex items-center gap-2">
                <Icon size={16} stroke={1.5} aria-hidden="true" />
                {name}
              </li>
            ))}
            <li className="flex items-center gap-2 text-muted-foreground">
              <IconBrandInstagram size={16} stroke={1.5} aria-hidden="true" />
              Instagram, later
            </li>
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
  { name: "Chidi O.", place: "Lagos", Icon: IconBrandWhatsapp, time: "2:14 am", snippet: "Thursday works. Please book it.", tag: { kind: "ai", text: "Booked by Ondra" }, selected: true },
  { name: "Alhaji M.", place: "Abuja", Icon: IconPhone, time: "1:52 am", snippet: "Missed call. Rang your mobile.", tag: { kind: "vip", text: "Waiting 2 h" }, vip: true },
  { name: "Sarah K.", place: "Dallas", Icon: IconMessage, time: "11:40 pm", snippet: "Do you take trade-ins on a 2019 Tahoe?", tag: { kind: "draft", text: "Draft waiting for you" } },
  { name: "Marcus T.", place: "Houston", Icon: IconPhone, time: "9:05 pm", snippet: "Asked about financing on the X5.", tag: { kind: "team", text: "With Daniel, Sales" } },
  { name: "Grace A.", place: "Accra", Icon: IconMail, time: "8:30 pm", snippet: "Shipping to Tema port, how long?", tag: { kind: "ai", text: "Sent by Ondra" } },
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
      {kind === "vip" ? <IconCrownFilled size={12} aria-hidden="true" /> : kind === "team" ? null : <IconSparkles size={12} stroke={2} aria-hidden="true" />}
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
          <h2 className="font-display text-h2 max-w-[15ch]">One inbox. You can see what the AI did.</h2>
          <p className="text-lead max-w-(--container-prose) text-fg-2">
            Every call, WhatsApp, text and email lands in one place. Anything Ondra said, drafted or booked is marked in
            blue with its name on it. VIPs never are.
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
                    <span className="rounded-pill bg-vip-subtle px-2.5 py-1 text-vip">Needs you 1</span>
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
                          {r.vip && <IconCrownFilled size={14} className="text-vip" aria-hidden="true" />}
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
                      <span className="flex size-9 items-center justify-center rounded-full bg-wa-subtle text-wa">
                        <IconBrandWhatsapp size={18} stroke={1.75} />
                      </span>
                      <div>
                        <p className="font-semibold">Chidi O.</p>
                        <p className="text-micro text-muted-foreground">WhatsApp</p>
                      </div>
                    </div>
                    <div className="text-micro flex gap-4 tabular-nums">
                      <span>
                        <span className="text-muted-foreground">Dallas </span>2:14 am
                      </span>
                      <span>
                        <span className="text-muted-foreground">Lagos </span>9:14 am
                      </span>
                    </div>
                  </div>
                  <dl className="text-micro mt-4 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-5">
                    {[
                      ["Vehicle", "2023 G63, black"],
                      ["Budget", "About $180k"],
                      ["Payment", "Wire transfer"],
                      ["Ships to", "Lagos"],
                      ["Timeline", "This month"],
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
                    <BuyerMessage meta="2:14 am">Good evening. Is the black 2023 G63 still available? Can you ship to Lagos?</BuyerMessage>
                  </Appear>

                  <Appear delay={0.5}>
                    <AiMessage meta="2:14 am">
                    Yes, it&apos;s on the lot: black, 18k miles, and we ship to Lagos regularly. Daniel can show it to you on a
                    live video walkaround. Would Thursday at 10 am Dallas time work? That&apos;s 5 pm for you.
                  </AiMessage>
                  </Appear>

                  <Appear delay={1.1}>
                    <BuyerMessage meta="2:16 am">Thursday works. Please book it.</BuyerMessage>
                  </Appear>

                  <Appear delay={1.6}>
                    <AiMessage meta="2:16 am">Booked. Daniel will call you on WhatsApp video on Thursday. Shipping costs are next on his list.</AiMessage>
                  </Appear>

                  <Appear delay={2.1}>
                    <div className="flex items-center gap-3 text-ai">
                    <span className="h-px flex-1 bg-ai/15" />
                    <span className="text-micro flex items-center gap-1.5 font-medium">
                      <IconCalendarEvent size={14} stroke={1.75} />
                      Video walkaround booked by Ondra for Thursday, 10:00 am
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
                      Cash buyer in Lagos, wants the black G63 shipped to Apapa. Asked about shipping costs. I didn&apos;t
                      quote. Please call before the walkaround.
                    </blockquote>
                    <div className="text-micro mt-3 flex flex-wrap gap-2">
                      <span className="rounded-pill bg-muted px-2.5 py-1">Due Thursday, 9:30 am</span>
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
      p: "A buyer calls about the black G63. The showroom closed at seven, so he calls the next dealer on his list.",
    },
    {
      t: "11:15 pm",
      p: "Three WhatsApp messages land on Daniel's personal phone. He's asleep, and nobody else can see them.",
    },
    {
      t: "2:14 am",
      p: "A buyer in Lagos, where it's 9:14 in the morning, asks about shipping. By the time you open, she has asked three other dealers.",
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
          <Lead className="mt-5 text-fg-2">Buyers don&apos;t wait for opening hours. Most dealerships make them.</Lead>
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

/* ---------------------------------------------------------------- whatsapp / cross-border */

function WhatsApp() {
  const points = [
    {
      t: "Your number, the official API",
      p: "Ondra connects your existing WhatsApp Business number through Meta's official API. No grey-market tools that get numbers banned.",
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
    <section id="whatsapp" className="on-dark scroll-mt-4 bg-night py-24 text-white sm:py-32 border-t border-line">
      <Wrap>
        <div className="grid gap-12 lg:grid-cols-[1.1fr_1fr] lg:items-center">
          <div>
            <H2 className="max-w-[16ch]">Built for buyers who live on WhatsApp.</H2>
            <Lead className="mt-5 text-white/70">
              Most dealer AI tools are built for US buyers on phone and text. Ondra is built for dealers whose buyers are
              in Lagos, Accra, Dubai or down the road, and would rather message than call.
            </Lead>
          </div>
          {/* Dual clock: the detail only a cross-border dealer cares about */}
          <figure className="rounded-panel border border-white/12 p-6 sm:p-8">
            <div className="grid grid-cols-2 divide-x divide-white/12">
              <div className="pr-6">
                <p className="text-small text-white/55">Your showroom, Dallas</p>
                <p className="font-display mt-2 text-[clamp(2rem,6vw,3.5rem)] font-bold leading-none tabular-nums">2:14</p>
                <p className="text-small mt-1 text-white/55">am, closed</p>
              </div>
              <div className="pl-6">
                <p className="text-small text-white/55">Your buyer, Lagos</p>
                <p className="font-display mt-2 text-[clamp(2rem,6vw,3.5rem)] font-bold leading-none text-brand-text tabular-nums">9:14</p>
                <p className="text-small mt-1 text-white/55">am, ready to buy</p>
              </div>
            </div>
            <figcaption className="text-small mt-6 flex items-start gap-2 border-t border-white/12 pt-5 text-white/75">
              <IconBrandWhatsapp size={18} stroke={1.5} className="mt-0.5 shrink-0 text-wa-on-dark" aria-hidden="true" />
              Answered in her morning. Booked into yours: a video walkaround with Daniel at 10 am Dallas time.
            </figcaption>
          </figure>
        </div>
        <ul className="mt-16 grid gap-x-10 gap-y-10 md:grid-cols-3">
          {points.map((i) => (
            <li key={i.t} className="border-t border-white/20 pt-5">
              <p className="font-display text-h4">{i.t}</p>
              <p className="mt-2.5 text-white/70">{i.p}</p>
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
    <section id="vip" className="scroll-mt-4 bg-bg py-24 sm:py-32 border-t border-line">
      <Wrap className="grid items-center gap-12 lg:grid-cols-2">
        <div>
          <H2 className="max-w-[15ch]">Some clients should only ever hear from you.</H2>
          <Lead className="mt-5 text-fg-2">
            Mark a client, or the people who buy for them, as VIP. Their calls ring you directly. Their messages wait for
            your personal reply. No AI answer, no AI draft, no voice agent, ever.
          </Lead>
          <p className="mt-4 max-w-[50ch] text-muted-foreground">If you miss the call, you get an alert straight away, not a summary at the end of the day.</p>
        </div>
        <div aria-hidden="true" className="mx-auto w-full max-w-[420px] space-y-3">
          <div className="rounded-card bg-surface p-5 shadow-float">
            <div className="flex items-center justify-between">
              <span className="text-small flex items-center gap-1.5 rounded-pill bg-vip-subtle px-2.5 py-1 font-semibold text-vip">
                <IconCrownFilled size={14} />
                VIP
              </span>
              <span className="text-small text-muted-foreground">Incoming call</span>
            </div>
            <p className="font-display mt-3 text-[22px] font-bold">Alhaji M.</p>
            <p className="text-small text-muted-foreground">Ringing your mobile. The voice agent stays off.</p>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <span className="rounded-control bg-ok py-2.5 text-center text-sm font-semibold text-white">Answer</span>
              <span className="rounded-control border border-line py-2.5 text-center text-sm font-semibold">Text back</span>
            </div>
          </div>
          <div className="rounded-card border border-line bg-surface p-4 text-[14px]">
            <p className="font-semibold">WhatsApp from Alhaji M.&apos;s manager</p>
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
              <span>Waiting for you</span>
              <span>AI replies off</span>
            </div>
          </div>
        </div>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- owner on WhatsApp */

function OwnerBriefing() {
  const lines = [
    ["2", "VIPs waiting for you"],
    ["5", "hot leads overnight, 3 from Nigeria"],
    ["4", "follow-ups ready to approve"],
    ["10", "bookings today: 3 test drives, 1 video walkaround, 6 service"],
  ];
  return (
    <section className="border-y border-line bg-bg-2 py-24 sm:py-32 border-t border-line">
      <Wrap className="grid items-center gap-12 lg:grid-cols-[1fr_1.05fr]">
        <div aria-hidden="true" className="order-2 mx-auto w-full max-w-[420px] rounded-panel bg-wa-wallpaper p-4 lg:order-1">
          <p className="text-micro pb-2 text-center text-muted-foreground">Today 7:30 am</p>
          <div className="max-w-[94%] rounded-card rounded-tl-none bg-surface px-4 py-3.5 text-[14.5px] leading-relaxed">
            <p className="font-semibold">Good morning. Here&apos;s today.</p>
            <ul className="mt-2 space-y-1">
              {lines.map(([n, t]) => (
                <li key={t} className="flex gap-2.5">
                  <b className="w-5 shrink-0 text-right tabular-nums">{n}</b>
                  <span>{t}</span>
                </li>
              ))}
            </ul>
            <div className="mt-3 grid grid-cols-2 gap-2 border-t border-white/10 pt-2.5 text-center text-[14px] font-semibold text-ai">
              <span>Approve all 4</span>
              <span>Review</span>
            </div>
          </div>
          <div className="ml-auto mt-2.5 flex max-w-[70%] items-center gap-2 rounded-card rounded-tr-none bg-wa-bubble px-3 py-2.5 text-[13px]">
            <span className="size-0 border-y-[5px] border-l-[8px] border-y-transparent border-l-fg" />
            <span className="h-1 flex-1 rounded bg-white/20" />
            <span className="text-muted-foreground tabular-nums">0:14</span>
          </div>
          <div className="mt-2.5 max-w-[85%] rounded-card rounded-tl-none bg-surface px-4 py-3 text-[14px]">
            Done. Task for Daniel: send Chidi the shipping quote by 3 pm. Chidi&apos;s profile is updated.
          </div>
        </div>
        <div className="order-1 lg:order-2">
          <H2 className="max-w-[15ch]">Run your morning from WhatsApp.</H2>
          <Lead className="mt-5 text-fg-2">
            A briefing before you get to the lot: who&apos;s waiting, what came in overnight, what&apos;s booked. Approve
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
    ["Approve first", "For the first week, every reply the AI writes waits for your approval. Switch on automatic replies when you trust them."],
    ["No promises you didn't make", "It won't commit to a final price, a discount or a delivery date unless your policy says it can."],
    ["Hands off when it should", "If it isn't sure, or a buyer is upset, it passes the conversation to a person with a brief, and alerts a manager if needed."],
    ["STOP means stop", "When a customer opts out, Ondra stops messaging them on every channel, straight away."],
    ["Learns your answers", "Questions it couldn't answer land in one list. Answer once and it uses your answer from then on."],
    ["Your data stays yours", "Each dealer's data is kept separate and encrypted, and is never used to train AI models."],
  ];
  return (
    <section className="bg-bg py-24 sm:py-32 border-t border-line">
      <Wrap>
        <H2 className="max-w-[18ch]">The AI works for you. You stay in charge.</H2>
        <dl className="mt-14 grid gap-x-12 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {items.map(([t, p]) => (
            <div key={t} className="border-t-2 border-fg/70 pt-5">
              <dt className="font-display text-h4">{t}</dt>
              <dd className="mt-2.5 text-fg-2">{p}</dd>
            </div>
          ))}
        </dl>
      </Wrap>
    </section>
  );
}

/* ---------------------------------------------------------------- setup */

function Setup() {
  const steps = [
    ["Connect your channels", "Forward your phone line and your sales and service email. Connect your WhatsApp Business number through Meta. Customers keep the details they already have."],
    ["Show the agents how you work", "Your hours, your stock, what can be booked, who handles what, and which clients are VIPs who always reach you."],
    ["Approve, then let go", "Watch the first week in draft mode and correct anything that's off. Turn on automatic replies channel by channel."],
  ];
  return (
    <section className="on-dark bg-night py-24 text-white sm:py-32 border-t border-line">
      <Wrap>
        <H2 className="max-w-[18ch]">Staff the desks without hiring.</H2>
        <Lead className="mt-5 text-white/70">
          Phone and email can be answered within days. WhatsApp goes live once Meta approves your business account, and
          we walk you through that.
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
            answering the kinds of questions you get, on WhatsApp and on the phone.
          </Lead>
          <div className="mt-10 border-t border-line pt-6">
            <p className="font-semibold">Who we&apos;re piloting with</p>
            <ul className="mt-3 space-y-3 text-fg-2">
              {[
                ["Exporters", "selling to buyers in Africa and the Middle East over WhatsApp"],
                ["Community dealers", "whose buyers would rather message than call"],
                ["Independent and franchised dealers", "across the US, with or without a DMS"],
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
              We&apos;re building Ondra with an independent luxury dealer in Dallas who exports to Nigeria. Pilot places
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
    ["Do my customers get a new phone number or WhatsApp?", "No. You keep your number, WhatsApp and email. Calls reach Ondra through call forwarding, either for every call or only when your team doesn't pick up. WhatsApp connects through Meta's official API, and email through forwarding or by connecting Gmail or Microsoft 365."],
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
  return (
    <footer className="on-dark bg-night py-12 text-white/65">
      <Wrap className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <Logo className="text-white" />
          <p className="text-small mt-3 max-w-[40ch]">AI agents that answer, book and route for car dealerships.</p>
        </div>
        <div className="text-small">
          <a href={`mailto:${CONTACT_EMAIL}`} className="hover:text-white hover:underline">
            {CONTACT_EMAIL}
          </a>
          <p className="mt-1">© {new Date().getFullYear()} Ondra (working name)</p>
        </div>
      </Wrap>
    </footer>
  );
}
