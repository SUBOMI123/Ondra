"use client";

import { SIGN_IN_URL } from "@/lib/config";
import MobileMenu from "./MobileMenu";
import { NAV_LINKS } from "./navLinks";
import Wordmark from "./Wordmark";

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
        <a href="#top" className="flex items-center no-underline">
          <Wordmark className="h-[19px] w-auto" />
        </a>
        <nav aria-label="Sections" className="flex items-center gap-6 text-small">
          {NAV_LINKS.map(([label, href]) => (
            <a key={href} href={href} className="hidden text-white/75 no-underline hover:text-white md:inline">
              {label}
            </a>
          ))}
          <a href={SIGN_IN_URL} className="hidden text-white/75 no-underline hover:text-white sm:inline md:border-l md:border-white/15 md:pl-6">
            Sign in
          </a>
          <a href="#demo" className="btn btn-primary min-h-10 px-4 text-sm">
            Book a demo
          </a>
          <MobileMenu className="-mr-2 md:hidden" />
        </nav>
      </div>
    </div>
  );
}
