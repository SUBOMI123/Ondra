import { IconBrandWhatsapp, IconCalendarEvent, IconCrownFilled, IconMail, IconMessage, IconPhone, IconTool, IconUser } from "@tabler/icons-react";

/**
 * How Ondra works, as a drawing: every channel flows into Ondra, Ondra hands each conversation to the
 * right place, and VIP calls take their own route straight to the owner without touching the AI.
 * Pure SVG + CSS (SMIL dots), no JS. Dots are hidden under reduced motion.
 */

const W = 1100;
const H = 470;
const pct = (x: number, y: number) => ({ left: `${(x / W) * 100}%`, top: `${(y / H) * 100}%` });

const IN = [
  { y: 70, label: "Texts", Icon: IconMessage },
  { y: 165, label: "Email", Icon: IconMail },
  { y: 260, label: "WhatsApp", Icon: IconBrandWhatsapp },
  { y: 355, label: "Calls", Icon: IconPhone },
];
const OUT = [
  { y: 70, title: "Daniel, Sales", detail: "Qualified buyer, brief attached", Icon: IconUser },
  { y: 165, title: "Calendar", detail: "Test drive booked, Thu 6:00 pm", Icon: IconCalendarEvent },
  { y: 260, title: "Service desk", detail: "Oil change, Bay 2", Icon: IconTool },
];
const CX = 550;
const CY = 212;
const inPath = (y: number) => `M 172 ${y} C 330 ${y}, 340 ${CY}, 440 ${CY}`;
const outPath = (y: number) => `M 660 ${CY} C 760 ${CY}, 770 ${y}, 885 ${y}`;
const VIP_PATH = "M 172 355 C 330 355, 360 430, 550 430 S 780 400, 885 400";

export default function ChannelFlow() {
  return (
    <section className="border-t border-line bg-bg py-24 sm:py-32">
      <div className="mx-auto w-full max-w-(--container-page) px-4 sm:px-7">
        <div className="grid gap-6 lg:grid-cols-2 lg:items-end">
          <h2 className="font-display text-h2 max-w-[15ch]">Every channel in. The right person out.</h2>
          <p className="text-lead max-w-(--container-prose) text-fg-2">
            Ondra picks up every call, text, email and WhatsApp message, works out what the buyer wants, and hands it to the right
            person with a brief. VIP calls skip it entirely.
          </p>
        </div>

        {/* Desktop: the drawing */}
        <div className="relative mt-16 hidden md:block" style={{ aspectRatio: `${W} / ${H}` }}>
          <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 size-full" aria-hidden="true">
            <defs>
              <linearGradient id="flow-in" x1="0" x2="1">
                <stop offset="0" style={{ stopColor: "var(--color-white)", stopOpacity: 0.06 }} />
                <stop offset="1" style={{ stopColor: "var(--color-brand)", stopOpacity: 0.45 }} />
              </linearGradient>
              <linearGradient id="flow-out" x1="0" x2="1">
                <stop offset="0" style={{ stopColor: "var(--color-brand)", stopOpacity: 0.45 }} />
                <stop offset="1" style={{ stopColor: "var(--color-white)", stopOpacity: 0.08 }} />
              </linearGradient>
            </defs>
            {IN.map((n) => (
              <path key={n.label} id={`in-${n.y}`} d={inPath(n.y)} fill="none" stroke="url(#flow-in)" strokeWidth="1.25" />
            ))}
            {OUT.map((n) => (
              <path key={n.title} id={`out-${n.y}`} d={outPath(n.y)} fill="none" stroke="url(#flow-out)" strokeWidth="1.25" />
            ))}
            <path id="vip-path" d={VIP_PATH} fill="none" className="stroke-vip" strokeOpacity="0.55" strokeWidth="1.25" strokeDasharray="4 6" />

            <g className="motion-reduce:hidden">
              {IN.map((n, i) => (
                <circle key={n.label} r="3" className="fill-ai">
                  <animateMotion dur="3.2s" begin={`${i * 0.8}s`} repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.4 0 0.2 1">
                    <mpath href={`#in-${n.y}`} />
                  </animateMotion>
                </circle>
              ))}
              {OUT.map((n, i) => (
                <circle key={n.title} r="3" className="fill-ai">
                  <animateMotion dur="3.2s" begin={`${1.6 + i * 0.8}s`} repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.4 0 0.2 1">
                    <mpath href={`#out-${n.y}`} />
                  </animateMotion>
                </circle>
              ))}
              <circle r="3.5" className="fill-vip">
                <animateMotion dur="4s" begin="0.4s" repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.4 0 0.2 1">
                  <mpath href="#vip-path" />
                </animateMotion>
              </circle>
            </g>
          </svg>

          {IN.map(({ y, label, Icon }) => (
            <div key={label} className="absolute -translate-x-1/2 -translate-y-1/2" style={pct(110, y)}>
              <div className="flex items-center gap-2.5 rounded-pill border border-line-strong bg-surface px-4 py-2.5 text-[15px] text-fg">
                <Icon size={18} stroke={1.5} aria-hidden="true" className="text-muted-foreground" />
                {label}
              </div>
            </div>
          ))}

          <div className="absolute -translate-x-1/2 -translate-y-1/2" style={pct(CX, CY)}>
            <div className="w-56 rounded-card border border-brand/40 bg-linear-to-b from-ai-subtle to-surface px-5 py-4 text-center">
              <p className="flex items-center justify-center gap-2 text-lg font-medium text-fg">
                <i aria-hidden="true" className="block size-2 rounded-full bg-brand" />
                Ondra
              </p>
              <p className="text-small mt-1 text-ai">Answers, qualifies, books</p>
            </div>
          </div>

          {OUT.map(({ y, title, detail, Icon }) => (
            <div key={title} className="absolute -translate-x-1/2 -translate-y-1/2" style={pct(985, y)}>
              <div className="w-52 rounded-card border border-line bg-surface px-4 py-3">
                <p className="flex items-center gap-2 text-[15px] font-medium text-fg">
                  <Icon size={16} stroke={1.5} aria-hidden="true" className="text-muted-foreground" />
                  {title}
                </p>
                <p className="text-small mt-0.5 text-muted-foreground">{detail}</p>
              </div>
            </div>
          ))}

          <div className="absolute -translate-x-1/2 -translate-y-1/2" style={pct(985, 400)}>
            <div className="w-52 rounded-card border border-vip/40 bg-vip-subtle px-4 py-3">
              <p className="flex items-center gap-2 text-[15px] font-medium text-vip">
                <IconCrownFilled size={15} aria-hidden="true" />
                You
              </p>
              <p className="text-small mt-0.5 text-fg-2">VIP calls ring you directly</p>
            </div>
          </div>
          <p className="text-small absolute -translate-x-1/2 text-vip" style={pct(550, 446)}>
            VIPs never reach the AI
          </p>
        </div>

        {/* Phones: the same story, stacked */}
        <div className="mt-12 md:hidden">
          <div className="flex flex-wrap gap-2">
            {IN.map(({ label, Icon }) => (
              <span key={label} className="flex items-center gap-2 rounded-pill border border-line-strong bg-surface px-3.5 py-2 text-[15px]">
                <Icon size={16} stroke={1.5} aria-hidden="true" className="text-muted-foreground" />
                {label}
              </span>
            ))}
          </div>
          <div aria-hidden="true" className="ml-6 h-8 w-px bg-brand/40" />
          <div className="rounded-card border border-brand/40 bg-ai-subtle px-5 py-4">
            <p className="flex items-center gap-2 text-lg font-medium">
              <i className="block size-2 rounded-full bg-brand" />
              Ondra
            </p>
            <p className="text-small mt-1 text-ai">Answers, qualifies, books</p>
          </div>
          <div aria-hidden="true" className="ml-6 h-8 w-px bg-brand/40" />
          <ul className="grid gap-2">
            {OUT.map(({ title, detail, Icon }) => (
              <li key={title} className="rounded-card border border-line bg-surface px-4 py-3">
                <p className="flex items-center gap-2 font-medium">
                  <Icon size={16} stroke={1.5} aria-hidden="true" className="text-muted-foreground" />
                  {title}
                </p>
                <p className="text-small text-muted-foreground">{detail}</p>
              </li>
            ))}
            <li className="rounded-card border border-vip/40 bg-vip-subtle px-4 py-3">
              <p className="flex items-center gap-2 font-medium text-vip">
                <IconCrownFilled size={15} aria-hidden="true" />
                You
              </p>
              <p className="text-small text-fg-2">VIP calls skip Ondra and ring you directly</p>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}
