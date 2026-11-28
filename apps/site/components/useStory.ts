"use client";

import { useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

/**
 * Drives a short product story (a chat being answered, a call ringing through, a draft being checked).
 *
 * Returns the current step. Server HTML and no-JS visitors get the final state (step = Infinity), so
 * nothing is hidden at rest. After mount, a story that is still below the fold rewinds to step 0 and
 * plays once when it scrolls into view, one step per entry in `delays` (ms after the previous step).
 * Reduced motion keeps the final state.
 */
export function useStory(delays: number[]) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const inView = useInView(ref, { once: true, margin: "0px 0px -18% 0px" });
  const [step, setStep] = useState(Number.POSITIVE_INFINITY);
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || reduce) return;
    if (el.getBoundingClientRect().top > window.innerHeight * 0.9) {
      setArmed(true);
      setStep(0);
    }
  }, [reduce]);

  useEffect(() => {
    if (!armed || !inView) return;
    const timers: ReturnType<typeof setTimeout>[] = [];
    let t = 0;
    delays.forEach((d, i) => {
      t += d;
      timers.push(setTimeout(() => setStep(i + 1), t));
    });
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [armed, inView]);

  return { ref, step };
}
