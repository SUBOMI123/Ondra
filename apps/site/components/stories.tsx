"use client";

/**
 * Product stories for the marketing page. Each one plays once when it scrolls into view and renders
 * its final state for no-JS visitors, crawlers and reduced motion (see useStory).
 * Illustrative content only: names, numbers and times are examples.
 */

import {
  IconBrandWhatsapp,
  IconCalendarEvent,
  IconCheck,
  IconUserCheck,
  IconPhone,
  IconPhoneCall,
  IconPlayerPlayFilled,
  IconSparkles,
} from "@tabler/icons-react";
import { VipInitials, VipTag } from "@/components/vip";
import { AnimatePresence, motion } from "motion/react";
import { useStory } from "./useStory";

const enter = { initial: { opacity: 0, y: 8, scale: 0.98 }, animate: { opacity: 1, y: 0, scale: 1 }, exit: { opacity: 0 }, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const } };

/* ------------------------------------------------------------------ Sales: an after-hours text thread */

function Bubble({ me = false, ai = false, time, children }: { me?: boolean; ai?: boolean; time: string; children: React.ReactNode }) {
  return (
    <motion.div {...enter} className={`max-w-[84%] ${me ? "ml-auto" : ""}`}>
      <div className={`rounded-2xl px-3.5 py-2.5 ${me ? "rounded-br-md border border-ai/20 bg-ai-subtle text-fg" : "rounded-bl-md bg-muted text-fg"}`}>{children}</div>
      <p className={`text-micro mt-1 flex items-center gap-1 font-mono ${me ? "justify-end text-ai" : "text-muted-foreground"}`}>
        {ai && <IconSparkles size={11} stroke={2} aria-hidden="true" />}
        {ai ? `Ondra ${time}` : time}
      </p>
    </motion.div>
  );
}

function Dots() {
  return (
    <motion.div {...enter} className="ml-auto flex w-14 items-center justify-center gap-1 rounded-2xl border border-ai/20 bg-ai-subtle px-3 py-3" aria-label="typing">
      {[0, 1, 2].map((i) => (
        <motion.span key={i} className="block size-1.5 rounded-full bg-ai" animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }} />
      ))}
    </motion.div>
  );
}

export function SalesThread() {
  // 1 buyer, 2 typing, 3 Ondra reply, 4 buyer, 5 typing, 6 Ondra reply, 7 booking card
  const { ref, step } = useStory([500, 900, 1600, 1400, 800, 1400, 700]);
  return (
    <div ref={ref} data-story="sales" className="mx-auto w-full max-w-[360px]">
      <div className="overflow-hidden rounded-[2.4rem] border border-line-strong bg-bg p-2 shadow-[0_40px_90px_-40px_rgb(0_0_0/0.9)]">
        <div className="rounded-[2rem] bg-surface">
          <div className="flex flex-col items-center gap-1 border-b border-line px-4 pb-3 pt-5">
            <span className="flex size-10 items-center justify-center rounded-full bg-muted text-sm font-medium">PM</span>
            <p className="text-[14px] font-medium leading-tight">Prestige Motors</p>
            <p className="text-micro text-muted-foreground">Text message</p>
          </div>
          <div className="flex min-h-[470px] flex-col gap-3 px-3.5 py-4 text-[14px] leading-snug">
            <p className="text-micro mx-auto text-muted-foreground">Tuesday 10:48 pm</p>
            <AnimatePresence initial={false}>
              {step >= 1 && (
                <Bubble key="b1" time="10:48 pm">
                  Hi, is the white 2021 Highlander still there? Need a third row, budget around $35k.
                </Bubble>
              )}
              {step === 2 && <Dots key="t1" />}
              {step >= 3 && (
                <Bubble key="r1" me ai time="10:48 pm">
                  It is: 41k miles, listed at $33,900. We also have a 2022 Pilot with a third row listed at $34,500. Want to see both on
                  Saturday?
                </Bubble>
              )}
              {step >= 4 && (
                <Bubble key="b2" time="10:51 pm">
                  Saturday morning. I&apos;ve got a 2017 Civic to trade.
                </Bubble>
              )}
              {step === 5 && <Dots key="t2" />}
              {step >= 6 && (
                <Bubble key="r2" me ai time="10:51 pm">
                  Booked for Saturday at 10 am with Daniel. Bring the Civic and we&apos;ll appraise it while you drive.
                </Bubble>
              )}
              {step >= 7 && (
                <motion.div key="card" {...enter} className="mt-1 flex items-center gap-2.5 rounded-card border border-line bg-bg px-3 py-2.5">
                  <IconCalendarEvent size={16} stroke={1.75} className="text-ai" aria-hidden="true" />
                  <span className="text-micro flex-1">
                    <span className="block font-medium text-fg">Test drive, Sat 10:00 am</span>
                    <span className="text-muted-foreground">Highlander and Pilot pulled up, trade appraisal</span>
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
      <p className="text-small mt-4 text-center text-muted-foreground">Texted at 10:48 pm. The showroom closed at eight.</p>
    </div>
  );
}

/* ------------------------------------------------------------------ Service: a call answered live */

const CALL = [
  { who: "caller", t: "Hi, my check engine light came on, and I think I'm due an oil change anyway." },
  { who: "ondra", t: "I can get you in. Is this for the 2019 F-150 on your account?" },
  { who: "caller", t: "That's the one." },
  { who: "ondra", t: "Tomorrow at 7:30 am works. I'll ask your advisor to check the light while it's in. Do you need a loaner?" },
  { who: "caller", t: "Yes, please." },
];

export function ServiceCall() {
  // 1-5 transcript lines, 6 booking lands
  const { ref, step } = useStory([500, 1300, 1500, 900, 1700, 900]);
  const live = step >= 1 && step < 6;
  return (
    <div ref={ref} data-story="service" className="mx-auto w-full max-w-[460px] rounded-panel border border-line bg-surface">
      <div className="flex items-center gap-3 border-b border-line px-5 py-4">
        <span className="flex size-10 items-center justify-center rounded-full bg-ai-subtle text-ai">
          <IconPhone size={18} stroke={1.75} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-medium">Service line</p>
          <p className="text-micro text-muted-foreground">Answered by Ondra on the first ring</p>
        </div>
        <span className="flex h-6 items-center gap-[3px]" aria-hidden="true">
          {Array.from({ length: 9 }).map((_, i) => (
            <motion.span
              key={i}
              className="block w-[3px] rounded-full bg-ai"
              initial={false}
              animate={live ? { height: [4, 6 + ((i * 5) % 14), 4] } : { height: 4 }}
              transition={{ duration: 0.9, repeat: live ? Infinity : 0, delay: i * 0.06 }}
              style={{ height: 4 }}
            />
          ))}
        </span>
        <span className="text-micro font-mono tabular-nums text-muted-foreground">{step >= 6 ? "1:12" : "0:41"}</span>
      </div>
      <ol className="grid min-h-[17rem] content-start gap-3 px-5 py-5 text-[14.5px] leading-snug">
        {CALL.map((l, i) => (
          <motion.li
            key={i}
            initial={false}
            animate={{ opacity: step >= i + 1 ? 1 : 0, y: step >= i + 1 ? 0 : 6 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="grid grid-cols-[4.5rem_1fr] gap-3"
          >
            <span className={`text-micro pt-0.5 font-medium ${l.who === "ondra" ? "flex items-start gap-1 text-ai" : "text-muted-foreground"}`}>
              {l.who === "ondra" && <IconSparkles size={11} stroke={2} className="mt-0.5" aria-hidden="true" />}
              {l.who === "ondra" ? "Ondra" : "Caller"}
            </span>
            <span className={l.who === "ondra" ? "text-fg" : "text-fg-2"}>{l.t}</span>
          </motion.li>
        ))}
      </ol>
      <motion.div
        initial={false}
        animate={{ opacity: step >= 6 ? 1 : 0.25 }}
        transition={{ duration: 0.4 }}
        className="grid grid-cols-3 gap-px overflow-hidden rounded-b-panel border-t border-line bg-line text-micro"
      >
        {[
          ["Booked", "Wed 7:30 am, Bay 3"],
          ["Advisor", "Maria, brief sent"],
          ["Loaner", "Requested"],
        ].map(([k, v]) => (
          <div key={k} className="bg-surface px-4 py-3">
            <p className="text-muted-foreground">{k}</p>
            <p className="mt-0.5 font-medium text-fg">{v}</p>
          </div>
        ))}
      </motion.div>
    </div>
  );
}

/* ------------------------------------------------------------------ VIP call */

const VIP_STEPS = [
  { t: "Incoming call from Robert Hale", d: "+1 (214) ••• 4471", Icon: IconPhone },
  { t: "Recognised as a VIP", d: "Marked by you in 2023", Icon: IconUserCheck, vip: true },
  { t: "Ondra stays off this call", d: "No AI answer, no AI draft", Icon: IconSparkles, off: true },
  { t: "Ringing Daniel, who looks after them", d: "No answer? Your own words, then your front desk", Icon: IconPhoneCall, ring: true },
];

export function VipCall() {
  const { ref, step } = useStory([500, 800, 800, 800]);
  return (
    <div ref={ref} data-story="vip" className="mx-auto w-full max-w-[440px] rounded-card border border-line bg-surface p-5 sm:p-6">
      <div className="flex items-center gap-4">
        <div className="relative flex size-14 items-center justify-center">
          <VipInitials name="Robert Hale" className="size-14 text-base" />
          {step >= 4 && (
            <>
              <span className="absolute inset-0 rounded-full border border-vip/50 motion-safe:animate-[ring_1.6s_ease-out_infinite]" />
              <span className="absolute inset-0 rounded-full border border-vip/40 motion-safe:animate-[ring_1.6s_ease-out_0.5s_infinite]" />
            </>
          )}
        </div>
        <div>
          <p className="text-lg font-medium">Robert Hale</p>
          <p className="text-small text-muted-foreground">Bought six cars from you</p>
        </div>
        <VipTag className="ml-auto" />
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

/* ------------------------------------------------------------------ Morning briefing */

const BRIEF = [
  ["2", "VIPs waiting for you"],
  ["5", "hot leads overnight, 2 after midnight"],
  ["4", "follow-ups ready to approve"],
  ["10", "bookings today: 4 test drives, 6 service"],
];

export function Briefing() {
  // 1-4 lines, 5 approve pressed, 6 voice note, 7 Ondra reply
  const { ref, step } = useStory([400, 450, 450, 450, 1300, 1100, 1400]);
  return (
    <div ref={ref} data-story="briefing" className="mx-auto w-full max-w-[420px] rounded-panel bg-wa-wallpaper p-4">
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
            Done. Task for Daniel: call Jordan about the Civic trade-in by noon. Jordan&apos;s profile is updated.
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
    <div ref={ref} data-story="policy" className="rounded-panel border border-line bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-small flex items-center gap-1.5 text-ai">
          <IconSparkles size={14} stroke={1.75} aria-hidden="true" />
          Draft by Ondra, reply to Jordan P.
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
              <span className={`rounded px-1 transition-colors duration-300 ${flaggedPrice ? "bg-dusk/20 text-dusk line-through decoration-dusk" : ""}`}>$31,500 out the door</span>{" "}
              and have it{" "}
              <span className={`rounded px-1 transition-colors duration-300 ${flaggedDate ? "bg-dusk/20 text-dusk line-through decoration-dusk" : ""}`}>ready for you by Friday</span>.
            </motion.p>
          ) : (
            <motion.p key="rewrite" {...enter} className="text-lead leading-relaxed text-fg">
              It&apos;s on the lot and it&apos;s yours to drive on Saturday. Daniel will go through the final price, your trade-in and
              timing with you then.
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
