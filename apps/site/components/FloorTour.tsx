"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The walk through the dealership, told in five photographs.
 *
 * Cinematic mode (default): a sticky stage. Each scene dollies in slowly as you scroll and the
 * next one crossfades over it. On phones the camera pans across each scene so both desks get
 * their moment instead of being cropped away. Labels are pinned to points in the photograph and
 * follow the zoom and pan.
 *
 * Static mode (reduced motion, or before JS runs): the same scenes as a plain sequence of
 * figures with the labels listed under each one. Nothing is hidden.
 *
 * Images are generated (see docs/DECISIONS.md). No badges, plates or people.
 */

type Label = { u: number; v: number; role: string; name: string; doing: string; vip?: boolean };
type Scene = {
  src: string;
  alt: string;
  title?: string;
  line?: string;
  vip?: boolean;
  /** Focus point for the dolly, as fractions of the image */
  focus: [number, number];
  /** Horizontal pan on narrow screens: object-position x from, to */
  pan: [number, number];
  labels: Label[];
};

const IMG_W = 1536;
const IMG_H = 864;

const SCENES: Scene[] = [
  {
    src: "/floor/entrance",
    alt: "Walking into a dealership showroom at night: cars on both sides of the aisle, robots at desks further down, a glass office at the end",
    focus: [0.5, 0.47],
    pan: [0.5, 0.5],
    labels: [],
  },
  {
    src: "/floor/desks-1",
    alt: "A robot in a headset taking a phone call at a walnut desk, and a second robot replying to messages on two monitors, with a black SUV and a silver coupe behind them",
    title: "Reception and WhatsApp",
    line: "Calls picked up on the first ring. Messages answered in seconds, at any hour.",
    focus: [0.5, 0.4],
    pan: [0.12, 0.84],
    labels: [
      { u: 0.166, v: 0.24, role: "Voice agent", name: "Reception", doing: "Answering a call about a black G63" },
      { u: 0.8, v: 0.28, role: "Messaging agent", name: "WhatsApp and email", doing: "Replying to a buyer in Lagos with photos" },
    ],
  },
  {
    src: "/floor/desks-2",
    alt: "A robot booking test drives on a calendar, car keys on a tray beside it, and a second robot scheduling service with the workshop visible through glass",
    title: "Bookings and service",
    line: "Test drives, video walkarounds and service slots, booked against your real calendars.",
    focus: [0.45, 0.45],
    pan: [0.1, 0.86],
    labels: [
      { u: 0.14, v: 0.27, role: "Booking agent", name: "Test drives and visits", doing: "Booking a video walkaround for Thursday" },
      { u: 0.83, v: 0.33, role: "Service agent", name: "Service desk", doing: "Fitting an oil change into Bay 2" },
    ],
  },
  {
    src: "/floor/desks-3",
    alt: "A standing robot holding a tablet, passing work on, and a seated robot drafting follow-up messages, with a bronze sedan on display behind",
    title: "Handoffs and follow-ups",
    line: "The right buyer to the right person, with a brief. Follow-ups wait for your approval.",
    focus: [0.5, 0.4],
    pan: [0.14, 0.9],
    labels: [
      { u: 0.195, v: 0.14, role: "Routing agent", name: "Handoffs", doing: "Sending a qualified buyer to Daniel in Sales" },
      { u: 0.9, v: 0.28, role: "Follow-up agent", name: "Follow-ups", doing: "Drafting nudges for buyers who went quiet" },
    ],
  },
  {
    src: "/floor/office",
    alt: "The owner's empty glass office at night: a walnut desk, a leather chair, a brass lamp and a desk phone with a red light",
    title: "Your office",
    line: "VIP calls skip the agents and ring straight through to you.",
    vip: true,
    focus: [0.58, 0.48],
    pan: [0.45, 0.62],
    labels: [{ u: 0.61, v: 0.44, role: "Not an agent", name: "Your office", doing: "A VIP is calling. It rings you, not the AI.", vip: true }],
  },
];

const srcSet = (s: string) => `${s}-960.jpg 960w, ${s}.jpg 1536w`;
const clamp = (x: number, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const smooth = (x: number) => x * x * (3 - 2 * x);

function LabelCard({ l, className = "", style }: { l: Label; className?: string; style?: React.CSSProperties }) {
  return (
    <div className={`floor-label ${l.vip ? "vip" : ""} ${className}`} style={style}>
      <span className="role">
        <i />
        {l.role}
      </span>
      <b>{l.name}</b>
      <span className="doing">{l.doing}</span>
    </div>
  );
}

export default function FloorTour() {
  const [mode, setMode] = useState<"static" | "cinematic">("static");

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const set = () => setMode(mq.matches ? "static" : "cinematic");
    set();
    mq.addEventListener("change", set);
    return () => mq.removeEventListener("change", set);
  }, []);

  return mode === "cinematic" ? <Cinematic /> : <StaticTour />;
}

/* ------------------------------------------------------------------ static */

function StaticTour() {
  return (
    <section id="walkthrough" aria-label="Walk the dealership floor" className="on-dark bg-ink py-20 text-white sm:py-28">
      <div className="mx-auto w-full max-w-(--container-page) px-4 sm:px-7">
        <h2 className="font-display text-h2 max-w-[14ch]">Walk in. Every desk is staffed.</h2>
        <div className="mt-12 space-y-16">
          {SCENES.slice(1).map((s) => (
            <figure key={s.src}>
              <img
                src={`${s.src}.jpg`}
                srcSet={srcSet(s.src)}
                sizes="(min-width: 1216px) 1216px, 100vw"
                width={IMG_W}
                height={IMG_H}
                loading="lazy"
                alt={s.alt}
                className="aspect-video w-full rounded-panel object-cover"
              />
              <figcaption className="mt-5 grid gap-5 md:grid-cols-[1fr_1.4fr]">
                <div>
                  <p className={`font-display text-h3 ${s.vip ? "text-vip-on-dark" : ""}`}>{s.title}</p>
                  <p className="mt-2 text-white/70">{s.line}</p>
                </div>
                <ul className="grid gap-3 sm:grid-cols-2">
                  {s.labels.map((l) => (
                    <li key={l.name}>
                      <LabelCard l={l} className="no-stem !max-w-none" />
                    </li>
                  ))}
                </ul>
              </figcaption>
            </figure>
          ))}
        </div>
        <p className="font-display text-h2 mt-20 max-w-[16ch]">None of them are people. All of them are on your side.</p>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ cinematic */

function Cinematic() {
  const sectionRef = useRef<HTMLElement>(null);
  const sceneRefs = useRef<(HTMLDivElement | null)[]>([]);
  const imgRefs = useRef<(HTMLImageElement | null)[]>([]);
  const capRefs = useRef<(HTMLDivElement | null)[]>([]);
  const labelRefs = useRef<(HTMLDivElement | null)[][]>(SCENES.map(() => []));
  const introRef = useRef<HTMLDivElement>(null);
  const outroRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const section = sectionRef.current!;
    const N = SCENES.length;
    let raf = 0;

    const render = () => {
      raf = 0;
      const W = window.innerWidth;
      const H = window.innerHeight;
      const r = section.getBoundingClientRect();
      if (r.bottom < 0 || r.top > H) return;
      const p = clamp(-r.top / (section.offsetHeight - H));
      const narrow = W / H < 1.2; // portrait-ish: pan across the scene
      if (progressRef.current) progressRef.current.style.transform = `scaleX(${p})`;

      const outro = smooth(clamp((p * N - (N - 1) - 0.55) / 0.25));
      for (let i = 0; i < N; i++) {
        const s = SCENES[i];
        const seg = p * N - i; // <0 before, 0..1 during, >1 after
        const t = clamp(seg, -0.2, 1.2);
        const el = sceneRefs.current[i];
        const img = imgRefs.current[i];
        if (!el || !img) continue;

        // Crossfade: each later scene fades in over the start of its segment.
        const fade = i === 0 ? 1 : smooth(clamp((seg + 0.18) / 0.3));
        el.style.opacity = String(fade);
        el.style.visibility = fade === 0 || seg > 1.6 ? "hidden" : "visible";

        // Camera: slow dolly towards the focus point, and a pan on narrow screens.
        const k = 1 + 0.1 * smooth(clamp((t + 0.2) / 1.4));
        // object-fit: cover geometry, so labels can follow points in the photo
        const sc = Math.max(W / IMG_W, H / IMG_H);
        const dw = IMG_W * sc;
        const dh = IMG_H * sc;
        // On narrow screens pan from one desk to the other: hold, move, hold.
        let px = 0.5;
        if (narrow && dw > W) {
          const aim = (u: number) => clamp((u * dw - W / 2) / (dw - W));
          const [a, b] =
            s.labels.length >= 2
              ? [aim(s.labels[0].u), aim(s.labels[s.labels.length - 1].u)]
              : s.labels.length === 1
                ? [aim(s.labels[0].u), aim(s.labels[0].u)]
                : s.pan;
          px = a + (b - a) * smooth(clamp((t - 0.38) / 0.27));
        }
        img.style.objectPosition = `${px * 100}% 50%`;
        const ox = (W - dw) * px;
        const oy = (H - dh) * 0.5;
        const fx = ox + s.focus[0] * dw;
        const fy = oy + s.focus[1] * dh;
        img.style.transformOrigin = `${fx}px ${fy}px`;
        img.style.transform = `scale(${k})`;

        // Caption
        const cap = capRefs.current[i];
        if (cap) {
          const c = smooth(clamp((seg - 0.08) / 0.15)) * (1 - smooth(clamp((seg - 0.9) / 0.15))) * (1 - outro);
          cap.style.opacity = String(c);
          cap.style.transform = `translateY(${(1 - c) * 10}px)`;
        }

        // Labels, staggered, pinned to their point in the photo
        s.labels.forEach((l, j) => {
          const lab = labelRefs.current[i][j];
          if (!lab) return;
          const x0 = ox + l.u * dw;
          const y0 = oy + l.v * dh;
          const x = fx + (x0 - fx) * k;
          const y = fy + (y0 - fy) * k;
          const start = narrow ? 0.1 : 0.12 + j * 0.14;
          let vis = smooth(clamp((seg - start) / 0.12)) * (1 - smooth(clamp((seg - 0.92) / 0.1))) * (1 - outro);
          // Fade at the screen edges so a label leaves with its desk during a pan.
          vis *= smooth(clamp((x - W * 0.04) / (W * 0.14))) * smooth(clamp((W * 0.96 - x) / (W * 0.14)));
          lab.style.opacity = String(vis);
          const lw = lab.offsetWidth;
          const lx = clamp(x - lw / 2, 12, W - lw - 12);
          const ly = Math.max(72, y - lab.offsetHeight - 26);
          lab.style.transform = `translate(${lx}px, ${ly}px)`;
        });
      }

      // Intro over the entrance, outro over the office
      if (introRef.current) introRef.current.style.opacity = String(1 - smooth(clamp((p * N - 0.35) / 0.35)));
      if (outroRef.current) {
        outroRef.current.style.opacity = String(outro);
        outroRef.current.style.pointerEvents = outro > 0.5 ? "auto" : "none";
      }
    };

    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(render);
    };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    // Images change label geometry only via natural size, which is fixed; render once now.
    render();
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <section
      ref={sectionRef}
      id="walkthrough"
      aria-label="Walk the dealership floor"
      className="on-dark relative bg-ink text-white"
      style={{ height: `${SCENES.length * 120 + 40}svh` }}
    >
      <div className="sticky top-0 h-svh overflow-hidden">
        {SCENES.map((s, i) => (
          <div
            key={s.src}
            ref={(el) => {
              sceneRefs.current[i] = el;
            }}
            className="absolute inset-0"
            style={{ opacity: i === 0 ? 1 : 0 }}
          >
            <img
              ref={(el) => {
                imgRefs.current[i] = el;
              }}
              src={`${s.src}.jpg`}
              srcSet={srcSet(s.src)}
              sizes="100vw"
              width={IMG_W}
              height={IMG_H}
              alt={s.alt}
              loading={i < 2 ? "eager" : "lazy"}
              decoding="async"
              className="absolute inset-0 size-full object-cover will-change-transform"
            />
            {/* Scrim for legibility of captions, strongest at the bottom-left */}
            <div aria-hidden="true" className="absolute inset-0 bg-linear-to-t from-ink/85 via-ink/10 to-ink/30" />
            {s.title && (
              <div
                ref={(el) => {
                  capRefs.current[i] = el;
                }}
                className="absolute inset-x-0 bottom-0 mx-auto w-full max-w-(--container-page) px-4 pb-12 opacity-0 sm:px-7 sm:pb-16"
              >
                <p className={`font-display text-h2 max-w-[16ch] ${s.vip ? "text-vip-on-dark" : ""}`}>{s.title}</p>
                <p className="text-lead mt-3 max-w-[40ch] text-white/80">{s.line}</p>
              </div>
            )}
            <div aria-hidden="true" className="pointer-events-none absolute inset-0">
              {s.labels.map((l, j) => (
                <div
                  key={l.name}
                  ref={(el) => {
                    labelRefs.current[i][j] = el;
                  }}
                  className="absolute left-0 top-0"
                >
                  <LabelCard l={l} />
                </div>
              ))}
            </div>
          </div>
        ))}

        <div ref={introRef} className="pointer-events-none absolute inset-x-0 bottom-0 mx-auto w-full max-w-(--container-page) px-4 pb-14 sm:px-7 sm:pb-20">
          <h2 className="font-display max-w-[13ch] text-[clamp(2.25rem,1.4rem+3.6vw,4.5rem)] font-extrabold leading-[0.98] tracking-[-0.02em]">Walk in. Every desk is staffed.</h2>
          <p className="text-small mt-4 text-white/60">Keep scrolling to walk the floor</p>
        </div>

        <div ref={outroRef} className="absolute inset-0 flex items-center justify-center bg-ink/80 px-4 text-center opacity-0">
          <div>
            <p className="font-display mx-auto max-w-[15ch] text-[clamp(2.25rem,1.4rem+3.8vw,4.75rem)] font-extrabold leading-[0.98] tracking-[-0.02em]">
              None of them are people. All of them are on your side.
            </p>
            <p className="text-lead mx-auto mt-5 max-w-[42ch] text-white/75">
              Ondra&apos;s agents answer, book and route. Your team takes the handoffs that need a person.
            </p>
          </div>
        </div>

        {/* Thin progress line: where you are on the floor */}
        <div aria-hidden="true" className="absolute inset-x-0 top-0 h-[2px] bg-white/10">
          <div ref={progressRef} className="h-full origin-left scale-x-0 bg-sodium" />
        </div>
      </div>
    </section>
  );
}
