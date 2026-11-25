"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The walk through the dealership.
 *
 * Cinematic mode (default): a sticky stage that plays a rendered camera walk down the aisle,
 * scrubbed by scroll (never timed). The walk is a 180-frame image sequence (public/walk for
 * landscape, public/walk-portrait for phones) drawn on a canvas. Each desk's label is pinned to
 * its screen position in every frame, from the anchors.json written by design/3d/floor/render_walk.py.
 *
 * Static mode (reduced motion, or before JS runs): five photographs as a plain sequence of
 * figures with the labels listed under each one. Nothing is hidden.
 *
 * The walk is rendered in Blender (design/3d/README.md); the static photographs are generated
 * (docs/DECISIONS.md). No badges, plates or people.
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
    title: "Reception and messages",
    line: "Calls picked up on the first ring. Messages answered in seconds, at any hour.",
    focus: [0.5, 0.4],
    pan: [0.12, 0.84],
    labels: [
      { u: 0.166, v: 0.24, role: "Voice agent", name: "Reception", doing: "Answering a call about a Silverado" },
      { u: 0.8, v: 0.28, role: "Messaging agent", name: "Texts and email", doing: "Sending a buyer photos of the Highlander" },
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
      { u: 0.14, v: 0.27, role: "Booking agent", name: "Test drives and visits", doing: "Booking a test drive for Saturday" },
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
    <section id="walkthrough" aria-label="Walk the dealership floor" className="on-dark bg-night py-20 text-white sm:py-28">
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

type Anchors = { width: number; height: number; frames: { frame: number; anchors: Record<string, [number, number, boolean]> }[] };
type WalkLabel = { key: string; win: [number, number]; label: Label };
type WalkCaption = { title: string; line: string; win: [number, number]; vip?: boolean };

const N_FRAMES = 180;
// Frame windows come from the camera path: a label shows while its desk is ahead of the camera, within about 8 m and on screen, and only during its own caption so the two never disagree.
const WALK_LABELS: WalkLabel[] = [
  { key: "Reception", win: [36, 72], label: SCENES[1].labels[0] },
  { key: "Messages", win: [38, 72], label: SCENES[1].labels[1] },
  { key: "Bookings", win: [72, 100], label: SCENES[2].labels[0] },
  { key: "Service", win: [72, 106], label: SCENES[2].labels[1] },
  { key: "Handoffs", win: [106, 130], label: SCENES[3].labels[0] },
  { key: "Follow-ups", win: [106, 144], label: SCENES[3].labels[1] },
  { key: "Your office", win: [150, 174], label: SCENES[4].labels[0] },
];
const WALK_CAPTIONS: WalkCaption[] = [
  { title: SCENES[1].title!, line: SCENES[1].line!, win: [38, 72] },
  { title: SCENES[2].title!, line: SCENES[2].line!, win: [72, 106] },
  { title: SCENES[3].title!, line: SCENES[3].line!, win: [106, 148] },
  { title: SCENES[4].title!, line: SCENES[4].line!, win: [150, 172], vip: true },
];
const OUTRO_FROM = 170;

const frameUrl = (set: string, f: number) => `/${set}/frame_${String(f).padStart(4, "0")}.jpg`;
/** 0 outside the window, 1 inside, easing over `ramp` frames at each end */
const windowed = (f: number, [a, b]: [number, number], ramp = 6) => smooth(clamp((f - a) / ramp)) * (1 - smooth(clamp((f - (b - ramp)) / ramp)));

function Cinematic() {
  const sectionRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const capRefs = useRef<(HTMLDivElement | null)[]>([]);
  const labelRefs = useRef<(HTMLDivElement | null)[]>([]);
  const introRef = useRef<HTMLDivElement>(null);
  const outroRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const [portrait, setPortrait] = useState(false);

  // Phones get the 9:16 render and every second frame, to keep the download and memory small.
  useEffect(() => {
    const check = () => setPortrait(window.innerWidth / window.innerHeight < 1.2);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  useEffect(() => {
    const section = sectionRef.current!;
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    const set = portrait ? "walk-portrait" : "walk";
    const stride = portrait ? 2 : 1;
    const imgs: (HTMLImageElement | undefined)[] = new Array(N_FRAMES + 1);
    let anchors: Anchors | null = null;
    let raf = 0;
    let started = false;
    let alive = true;

    // Frame 1 first, then a coarse pass so scrubbing works early, then the rest, a few requests at a time.
    const order: number[] = [1];
    for (let f = 1; f <= N_FRAMES; f += 10) if (f !== 1) order.push(f);
    for (let f = 1; f <= N_FRAMES; f += stride) if (!order.includes(f)) order.push(f);
    const load = () => {
      if (started) return;
      started = true;
      fetch(`/${set}/anchors.json`)
        .then((r) => r.json())
        .then((a: Anchors) => {
          anchors = a;
          schedule();
        })
        .catch(() => {});
      let next = 0;
      const pump = () => {
        if (!alive || next >= order.length) return;
        const f = order[next++];
        const im = new Image();
        im.decoding = "async";
        im.onload = () => {
          imgs[f] = im;
          schedule();
          pump();
        };
        im.onerror = pump;
        im.src = frameUrl(set, f);
      };
      for (let k = 0; k < 6; k++) pump();
    };
    const io = new IntersectionObserver((e) => e[0].isIntersecting && load(), { rootMargin: "1200px 0px" });
    io.observe(section);

    const nearest = (f: number) => {
      for (let d = 0; d < N_FRAMES; d++) {
        if (imgs[f - d]) return imgs[f - d]!;
        if (imgs[f + d]) return imgs[f + d]!;
      }
      return undefined;
    };

    const render = () => {
      raf = 0;
      const W = window.innerWidth;
      const H = window.innerHeight;
      const r = section.getBoundingClientRect();
      if (r.bottom < 0 || r.top > H) return;
      const p = clamp(-r.top / (section.offsetHeight - H));
      const f = 1 + p * (N_FRAMES - 1);
      if (progressRef.current) progressRef.current.style.transform = `scaleX(${p})`;

      // Draw the frame with object-fit: cover geometry.
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
        canvas.width = Math.round(W * dpr);
        canvas.height = Math.round(H * dpr);
      }
      const im = nearest(Math.round(f));
      const iw = anchors?.width ?? im?.naturalWidth ?? 1600;
      const ih = anchors?.height ?? im?.naturalHeight ?? 900;
      const sc = Math.max(W / iw, H / ih);
      const dw = iw * sc;
      const dh = ih * sc;
      const ox = (W - dw) / 2;
      const oy = (H - dh) / 2;
      if (im) {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.drawImage(im, ox, oy, dw, dh);
      }

      const outro = smooth(clamp((f - OUTRO_FROM) / 7));
      WALK_CAPTIONS.forEach((c, i) => {
        const el = capRefs.current[i];
        if (!el) return;
        const v = windowed(f, c.win, 6) * (1 - outro);
        el.style.opacity = String(v);
        el.style.transform = `translateY(${(1 - v) * 10}px)`;
      });

      const fa = anchors?.frames[Math.min(N_FRAMES, Math.max(1, Math.round(f))) - 1]?.anchors;
      WALK_LABELS.forEach((l, j) => {
        const lab = labelRefs.current[j];
        if (!lab) return;
        const a = fa?.[l.key];
        let vis = a && a[2] ? windowed(f, l.win, 6) * (1 - outro) : 0;
        if (a) {
          const x = ox + a[0] * dw;
          const y = oy + a[1] * dh;
          // Fade at the screen edges so a label leaves with its desk.
          vis *= smooth(clamp((x - W * 0.04) / (W * 0.14))) * smooth(clamp((W * 0.96 - x) / (W * 0.14)));
          const lw = lab.offsetWidth;
          const lx = clamp(x - lw / 2, 12, W - lw - 12);
          const ly = Math.max(72, y - lab.offsetHeight - 26);
          lab.style.transform = `translate(${lx}px, ${ly}px)`;
        }
        lab.style.opacity = String(vis);
      });

      if (introRef.current) introRef.current.style.opacity = String(1 - smooth(clamp((f - 8) / 26)));
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
    render();
    return () => {
      alive = false;
      io.disconnect();
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [portrait]);

  return (
    <section
      ref={sectionRef}
      id="walkthrough"
      aria-label="Walk the dealership floor"
      className="on-dark relative bg-night text-white"
      style={{ height: "560svh" }}
    >
      <div className="sticky top-0 h-svh overflow-hidden">
        <canvas
          ref={canvasRef}
          role="img"
          aria-label="A walk down the aisle of a dealership showroom at night: cars on both sides, an AI agent at every desk, and the owner's empty glass office at the end"
          className="absolute inset-0 size-full"
        />
        {/* Scrim for legibility of captions, strongest at the bottom */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-linear-to-t from-night/85 via-night/10 to-night/30" />

        {WALK_CAPTIONS.map((c, i) => (
          <div
            key={c.title}
            ref={(el) => {
              capRefs.current[i] = el;
            }}
            className="absolute inset-x-0 bottom-0 mx-auto w-full max-w-(--container-page) px-4 pb-12 opacity-0 sm:px-7 sm:pb-16"
          >
            <p className={`font-display text-h2 max-w-[16ch] ${c.vip ? "text-vip-on-dark" : ""}`}>{c.title}</p>
            <p className="text-lead mt-3 max-w-[40ch] text-white/80">{c.line}</p>
          </div>
        ))}

        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          {WALK_LABELS.map((l, j) => (
            <div
              key={l.key}
              ref={(el) => {
                labelRefs.current[j] = el;
              }}
              className="absolute left-0 top-0 opacity-0"
            >
              <LabelCard l={l.label} />
            </div>
          ))}
        </div>

        <div ref={introRef} className="pointer-events-none absolute inset-x-0 bottom-0 mx-auto w-full max-w-(--container-page) px-4 pb-14 sm:px-7 sm:pb-20">
          <h2 className="font-display max-w-[13ch] text-[clamp(2.25rem,1.4rem+3.6vw,4.5rem)] font-extrabold leading-[0.98] tracking-[-0.02em]">Walk in. Every desk is staffed.</h2>
          <p className="text-small mt-4 text-white/60">Keep scrolling to walk the floor</p>
        </div>

        <div ref={outroRef} className="absolute inset-0 flex items-center justify-center bg-night/80 px-4 text-center opacity-0">
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
          <div ref={progressRef} className="h-full origin-left scale-x-0 bg-brand" />
        </div>
      </div>
    </section>
  );
}
