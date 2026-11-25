"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Scroll-driven walk down the dealership floor (concept from design/mockups/landing.html).
 *
 * - The scene (three.js + floor-scene.ts) is code-split and loaded only when this section
 *   comes near the viewport, so it never affects first paint.
 * - Visitors with reduced motion or no WebGL skip it; the agents grid carries the same content.
 * - The wall sign says "Your Dealership", not the pilot dealer's name (needs their permission).
 */

function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

export default function Walkthrough() {
  const sectionRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const introRef = useRef<HTMLDivElement>(null);
  const outroRef = useRef<HTMLDivElement>(null);
  const [enabled, setEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setEnabled(!reduce && webglAvailable());
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const section = sectionRef.current!;
    let cleanup: (() => void) | undefined;
    let cancelled = false;

    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        import("./floor-scene").then(({ mountScene }) => {
          if (cancelled) return;
          cleanup = mountScene({
            section,
            canvas: canvasRef.current!,
            labels: labelsRef.current!,
            intro: introRef.current!,
            outro: outroRef.current!,
          });
        });
      },
      { rootMargin: "800px 0px" },
    );
    io.observe(section);

    return () => {
      cancelled = true;
      io.disconnect();
      cleanup?.();
    };
  }, [enabled]);

  if (!enabled) return null;

  return (
    <section ref={sectionRef} id="walkthrough" aria-label="Walk the dealership floor" className="relative h-[480vh] bg-paper">
      <div className="sticky top-0 h-svh overflow-hidden bg-[#D9D3C9]">
        <canvas
          ref={canvasRef}
          className="block h-full w-full"
          aria-label="Inside the dealership: desks staffed by AI agents answering and routing calls and messages"
        />
        <div ref={labelsRef} aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden" />
        <div ref={introRef} className="pointer-events-none absolute inset-x-0 top-[14vh] mx-auto max-w-[1200px] px-6 text-ink">
          <h2 className="font-display max-w-[14ch] text-[clamp(32px,5vw,64px)] font-bold leading-[1] tracking-[-0.015em]">
            Walk in. Every desk is staffed.
          </h2>
          <p className="mt-4 text-[13px] text-muted-foreground">Keep scrolling</p>
        </div>
        <div
          ref={outroRef}
          className="absolute inset-0 flex flex-col items-center justify-center bg-paper/85 px-6 text-center text-ink opacity-0"
        >
          <h2 className="font-display max-w-[16ch] text-[clamp(32px,5.2vw,68px)] font-bold leading-[1] tracking-[-0.015em]">
            None of them are people. All of them are on your side.
          </h2>
          <p className="mt-4 max-w-[46ch] text-[18px] text-ink-2">
            Ondra&apos;s agents answer, book and route. Your team takes the handoffs that need a person.
          </p>
        </div>
      </div>
    </section>
  );
}
