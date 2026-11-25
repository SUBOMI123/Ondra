"use client";

import { useEffect, useState } from "react";

/** A compact bar that slides in once the hero is out of view, so "Book a demo" is always one tap away. */
export default function StickyNav() {
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const hero = document.getElementById("top");
    if (!hero) return;
    const io = new IntersectionObserver(([e]) => setShown(!e.isIntersecting), { rootMargin: "-80px 0px 0px 0px" });
    io.observe(hero);
    return () => io.disconnect();
  }, []);

  return (
    <div
      aria-hidden={!shown}
      inert={!shown}
      className={`on-dark fixed inset-x-0 top-0 z-40 border-b border-white/10 bg-night/95 text-white transition-[translate,opacity] duration-300 ease-out-expo motion-reduce:transition-none ${
        shown ? "translate-y-0 opacity-100" : "-translate-y-full opacity-0"
      }`}
    >
      <div className="mx-auto flex h-14 w-full max-w-(--container-page) items-center justify-between px-4 sm:px-7">
        <a href="#top" className="font-display flex items-center gap-2 text-lg font-bold no-underline">
          <i aria-hidden="true" className="block size-[9px] rounded-full bg-brand" />
          Ondra
        </a>
        <nav aria-label="Sections" className="flex items-center gap-6 text-small">
          {[
            ["The floor", "#walkthrough"],
            ["Inbox", "#how"],
            ["WhatsApp", "#whatsapp"],
            ["VIPs", "#vip"],
            ["FAQ", "#faq"],
          ].map(([label, href]) => (
            <a key={href} href={href} className="hidden text-white/75 no-underline hover:text-white lg:inline">
              {label}
            </a>
          ))}
          <a href="#demo" className="btn btn-primary min-h-10 px-4 text-sm">
            Book a demo
          </a>
        </nav>
      </div>
    </div>
  );
}
