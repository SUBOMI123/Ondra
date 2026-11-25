"use client";

/**
 * Product stories for the marketing page. Each one plays once when it scrolls into view and renders
 * its final state for no-JS visitors, crawlers and reduced motion (see useStory).
 * Illustrative content only: names, numbers and times are examples.
 */

import {
  IconBrandWhatsapp,
  IconCheck,
  IconCrownFilled,
  IconPhone,
  IconPhoneCall,
  IconPlayerPlayFilled,
  IconSparkles,
} from "@tabler/icons-react";
import { AnimatePresence, motion } from "motion/react";
import { useStory } from "./useStory";

const enter = { initial: { opacity: 0, y: 8, scale: 0.98 }, animate: { opacity: 1, y: 0, scale: 1 }, exit: { opacity: 0 }, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const } };

function Typing({ out = false }: { out?: boolean }) {
  return (
    <motion.div {...enter} className={`flex w-14 items-center justify-center gap-1 rounded-2xl px-3 py-3 ${out ? "ml-auto bg-wa-bubble" : "bg-wa-incoming"}`} aria-label="typing">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="block size-1.5 rounded-full bg-white/70"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ WhatsApp phone */

export function WhatsAppPhone() {
  // 1 buyer, 2 typing, 3 Ondra reply, 4 buyer, 5 typing, 6 Ondra reply
  const { ref, step } = useStory([500, 900, 1500, 1300, 800, 1400]);
  return (
    <div ref={ref} className="mx-auto w-full max-w-[340px]">
      <div className="overflow-hidden rounded-[2.4rem] border border-line-strong bg-wa-wallpaper p-2 shadow-[0_40px_90px_-40px_rgb(0_0_0/0.9)]">
        <div className="rounded-[2rem] bg-wa-wallpaper">
          <div className="flex items-center gap-3 rounded-t-[2rem] bg-wa-incoming px-4 pb-3 pt-5">
            <span className="flex size-9 items-center justify-center rounded-full bg-muted text-sm font-medium">PM</span>
            <div className="min-w-0">
              <p className="text-[15px] font-medium leading-tight">Prestige Motors Dallas</p>
              <p className="text-micro text-fg-2/70">{step === 2 || step === 5 ? "typing…" : "online"}</p>
            </div>
            <span className="text-micro ml-auto font-mono text-fg-2/60">9:14</span>
          </div>
          <div className="flex min-h-[430px] flex-col gap-2.5 px-3 py-4 text-[14px] leading-snug">
            <p className="text-micro mx-auto rounded-md bg-wa-incoming/80 px-2 py-0.5 text-fg-2/70">Today</p>
            <AnimatePresence initial={false}>
              {step >= 1 && (
                <motion.div key="b1" {...enter} className="max-w-[82%] rounded-2xl rounded-tl-md bg-wa-incoming px-3 py-2">
                  Good evening. Is the black 2023 G63 still available? Can you ship to Lagos?
                  <span className="text-micro mt-1 block text-right font-mono text-fg-2/50">9:14</span>
                </motion.div>
              )}
              {step === 2 && <Typing key="t1" out />}
              {step >= 3 && (
                <motion.div key="r1" {...enter} className="ml-auto max-w-[86%] rounded-2xl rounded-tr-md bg-wa-bubble px-3 py-2">
                  Yes, it&apos;s on the lot: black, 18k miles, and we ship to Lagos regularly. Would a live video walkaround with
                  Daniel help? Thursday 5 pm your time works.
                  <span className="text-micro mt-1 flex items-center justify-end gap-1 font-mono text-ai">
                    <IconSparkles size={11} stroke={2} />
                    Ondra 9:14
                  </span>
                </motion.div>
              )}
              {step >= 4 && (
                <motion.div key="b2" {...enter} className="max-w-[70%] rounded-2xl rounded-tl-md bg-wa-incoming px-3 py-2">
                  Thursday works. Please book it.
                  <span className="text-micro mt-1 block text-right font-mono text-fg-2/50">9:16</span>
                </motion.div>
              )}
              {step === 5 && <Typing key="t2" out />}
              {step >= 6 && (
                <motion.div key="r2" {...enter} className="ml-auto max-w-[86%] rounded-2xl rounded-tr-md bg-wa-bubble px-3 py-2">
                  Booked for Thursday, 5 pm Lagos time. Daniel will call you on WhatsApp video.
                  <span className="text-micro mt-1 flex items-center justify-end gap-1 font-mono text-ai">
                    <IconSparkles size={11} stroke={2} />
                    Ondra 9:16
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
      <p className="text-small mt-4 text-center text-muted-foreground">The buyer&apos;s phone in Lagos. Dallas is asleep.</p>
    </div>
  );
}

/* ------------------------------------------------------------------ VIP call */

const VIP_STEPS = [
  { t: "Incoming call from Alhaji M.", d: "+234 803 ••• 4471", Icon: IconPhone },
  { t: "Recognised as a VIP", d: "Marked by you in March", Icon: IconCrownFilled, vip: true },
  { t: "Ondra stays off this call", d: "No AI answer, no AI draft", Icon: IconSparkles, off: true },
  { t: "Ringing your mobile", d: "Then your office line, then a text", Icon: IconPhoneCall, ring: true },
];

export function VipCall() {
  const { ref, step } = useStory([500, 800, 800, 800]);
  return (
    <div ref={ref} className="mx-auto w-full max-w-[440px] rounded-card border border-line bg-surface p-5 sm:p-6">
      <div className="flex items-center gap-4">
        <div className="relative flex size-14 items-center justify-center rounded-full bg-vip-subtle text-vip">
          <IconCrownFilled size={22} aria-hidden="true" />
          {step >= 4 && (
            <>
              <span className="absolute inset-0 rounded-full border border-vip/50 motion-safe:animate-[ring_1.6s_ease-out_infinite]" />
              <span className="absolute inset-0 rounded-full border border-vip/40 motion-safe:animate-[ring_1.6s_ease-out_0.5s_infinite]" />
            </>
          )}
        </div>
        <div>
          <p className="text-lg font-medium">Alhaji M.</p>
          <p className="text-small text-muted-foreground">VIP since March</p>
        </div>
        <span className="text-micro ml-auto rounded-pill bg-vip-subtle px-2.5 py-1 font-medium text-vip">VIP</span>
      </div>
      <ol className="mt-6 grid gap-3">
        {VIP_STEPS.map((s, i) => {
          const on = step >= i + 1;
          return (
            <motion.li
              key={s.t}
              initial={false}
              animate={{ opacity: on ? 1 : 0.25, x: on ? 0 : -4 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="flex items-start gap-3"
            >
              <span
                className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full border ${
                  s.vip ? "border-vip/40 text-vip" : s.off ? "border-line text-muted-foreground" : s.ring ? "border-ok/40 text-ok" : "border-line-strong text-fg-2"
                }`}
              >
                <s.Icon size={14} stroke={1.75} aria-hidden="true" />
              </span>
              <div>
                <p className={`text-[15px] ${s.off ? "text-muted-foreground line-through decoration-muted-foreground/60" : "text-fg"}`}>{s.t}</p>
                <p className="text-small text-muted-foreground">{s.d}</p>
              </div>
            </motion.li>
          );
        })}
      </ol>
      <div className="mt-6 grid grid-cols-2 gap-2">
        <span className="rounded-pill bg-ok py-2.5 text-center text-sm font-medium text-night">Answer</span>
        <span className="rounded-pill border border-line-strong py-2.5 text-center text-sm">Text back</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Owner briefing */

const BRIEF = [
  ["2", "VIPs waiting for you"],
  ["5", "hot leads overnight, 3 from Nigeria"],
  ["4", "follow-ups ready to approve"],
  ["10", "bookings today: 3 test drives, 1 walkaround, 6 service"],
];

export function Briefing() {
  // 1-4 lines, 5 approve pressed, 6 voice note, 7 Ondra reply
  const { ref, step } = useStory([400, 450, 450, 450, 1300, 1100, 1400]);
  return (
    <div ref={ref} className="mx-auto w-full max-w-[420px] rounded-panel bg-wa-wallpaper p-4">
      <p className="text-micro pb-3 text-center font-mono text-fg-2/60">Today 7:30 am</p>
      <div className="max-w-[94%] rounded-2xl rounded-tl-md bg-wa-incoming px-4 py-3.5 text-[14.5px] leading-relaxed">
        <p className="flex items-center gap-1.5 font-medium">
          <IconBrandWhatsapp size={15} stroke={1.75} className="text-wa" aria-hidden="true" />
          Good morning. Here&apos;s today.
        </p>
        <ul className="mt-2 space-y-1">
          {BRIEF.map(([n, t], i) => (
            <motion.li key={t} initial={false} animate={{ opacity: step >= i + 1 ? 1 : 0, y: step >= i + 1 ? 0 : 4 }} transition={{ duration: 0.35 }} className="flex gap-2.5">
              <b className="w-6 shrink-0 text-right font-medium tabular-nums">{n}</b>
              <span className="text-fg-2">{t}</span>
            </motion.li>
          ))}
        </ul>
        <div className="mt-3 grid grid-cols-2 gap-2 border-t border-white/10 pt-3 text-center text-[14px] font-medium">
          <motion.span
            initial={false}
            animate={{ backgroundColor: step >= 5 ? "rgba(74,222,154,0.16)" : "rgba(0,0,0,0)" }}
            className="flex items-center justify-center gap-1.5 rounded-pill py-1.5 text-ai"
          >
            {step >= 5 ? (
              <>
                <IconCheck size={15} stroke={2} className="text-ok" aria-hidden="true" />
                <span className="text-ok">Approved</span>
              </>
            ) : (
              "Approve all 4"
            )}
          </motion.span>
          <span className="py-1.5 text-ai">Review</span>
        </div>
      </div>
      <AnimatePresence initial={false}>
        {step >= 6 && (
          <motion.div key="vn" {...enter} className="ml-auto mt-2.5 flex max-w-[74%] items-center gap-2.5 rounded-2xl rounded-tr-md bg-wa-bubble px-3 py-2.5">
            <IconPlayerPlayFilled size={14} aria-hidden="true" />
            <span className="flex h-6 flex-1 items-center gap-[3px]" aria-hidden="true">
              {Array.from({ length: 22 }).map((_, i) => (
                <motion.span
                  key={i}
                  className="block w-[3px] rounded-full bg-white/70"
                  initial={false}
                  animate={{ height: [6, 6 + ((i * 7) % 16), 6] }}
                  transition={{ duration: 1.2, repeat: step === 6 ? Infinity : 0, delay: i * 0.03 }}
                  style={{ height: 6 + ((i * 7) % 16) }}
                />
              ))}
            </span>
            <span className="text-micro font-mono text-fg-2/70">0:14</span>
          </motion.div>
        )}
        {step >= 7 && (
          <motion.div key="done" {...enter} className="mt-2.5 max-w-[88%] rounded-2xl rounded-tl-md bg-wa-incoming px-4 py-3 text-[14px]">
            Done. Task for Daniel: send Chidi the shipping quote by 3 pm. Chidi&apos;s profile is updated.
            <span className="text-micro mt-1 flex items-center gap-1 font-mono text-ai">
              <IconSparkles size={11} stroke={2} />
              Ondra 7:34
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------------ Guardrails: a draft checked against policy */

export function PolicyCheck() {
  // 1 price flagged, 2 date flagged, 3 rewrite, 4 ready
  const { ref, step } = useStory([700, 900, 1300, 900]);
  const flaggedPrice = step >= 1 && step < 3;
  const flaggedDate = step >= 2 && step < 3;
  return (
    <div ref={ref} className="rounded-panel border border-line bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-small flex items-center gap-1.5 text-ai">
          <IconSparkles size={14} stroke={1.75} aria-hidden="true" />
          Draft by Ondra, reply to Chidi O.
        </p>
        <motion.span
          initial={false}
          animate={{ opacity: 1 }}
          className={`text-micro rounded-pill px-2.5 py-1 font-medium ${step >= 4 ? "bg-ok/15 text-ok" : "bg-muted text-fg-2"}`}
        >
          {step >= 4 ? "Ready to send" : step >= 3 ? "Rewritten" : "Checking your policy"}
        </motion.span>
      </div>

      <div className="relative mt-5 min-h-[7.5rem]">
        <AnimatePresence mode="wait" initial={false}>
          {step < 3 ? (
            <motion.p key="draft" {...enter} className="text-lead leading-relaxed text-fg">
              Great news! I can do{" "}
              <span className={`rounded px-1 transition-colors duration-300 ${flaggedPrice ? "bg-dusk/20 text-dusk line-through decoration-dusk" : ""}`}>$172,000 cash</span>{" "}
              and have it{" "}
              <span className={`rounded px-1 transition-colors duration-300 ${flaggedDate ? "bg-dusk/20 text-dusk line-through decoration-dusk" : ""}`}>delivered to Lagos by Friday</span>.
            </motion.p>
          ) : (
            <motion.p key="rewrite" {...enter} className="text-lead leading-relaxed text-fg">
              It&apos;s on the lot and we ship to Lagos regularly. Daniel will confirm the final price and a delivery window with you
              on Thursday&apos;s call.
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      <div className="mt-5 grid gap-2 border-t border-line pt-5 sm:grid-cols-2">
        {[
          ["Final price", "Your policy: a person confirms prices", step >= 1],
          ["Delivery date", "Never promised without approval", step >= 2],
        ].map(([t, d, on]) => (
          <motion.div
            key={t as string}
            initial={false}
            animate={{ opacity: on ? 1 : 0.3 }}
            className="rounded-card border border-dusk/25 bg-dusk/[0.06] px-4 py-3"
          >
            <p className="text-small font-medium text-dusk">{t as string} held back</p>
            <p className="text-small text-muted-foreground">{d as string}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
