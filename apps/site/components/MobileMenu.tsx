"use client";

import { IconMenu2, IconX } from "@tabler/icons-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { NAV_LINKS } from "./navLinks";
import Wordmark from "./Wordmark";

/** Phone menu: a full-screen sheet with the section links and the demo button. Hidden from md up. */
export default function MobileMenu({ className = "" }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const reduce = useReducedMotion();
  const closeRef = useRef<HTMLButtonElement>(null);
  const openRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
      openRef.current?.focus();
    };
  }, [open]);

  const items = [["Walk the floor", "#walkthrough"], ...NAV_LINKS] as const;

  return (
    <div className={className}>
      <button
        ref={openRef}
        type="button"
        aria-label="Open menu"
        aria-expanded={open}
        onClick={() => setOpen(true)}
        className="flex size-11 items-center justify-center rounded-full text-white/85 hover:text-white"
      >
        <IconMenu2 size={22} stroke={1.6} aria-hidden="true" />
      </button>
      {/* Portalled to <body>: the sticky bar is transformed, which would trap a fixed sheet inside its 56px box. */}
      {typeof document !== "undefined" &&
        createPortal(
          <AnimatePresence>
            {open && (
              <motion.div
                role="dialog"
                aria-modal="true"
                aria-label="Menu"
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="on-dark fixed inset-0 z-50 flex flex-col bg-night text-white"
              >
                <div className="flex h-[76px] items-center justify-between px-4 sm:px-7">
                  <a
                    href="#top"
                    onClick={() => setOpen(false)}
                    className="no-underline"
                  >
                    <Wordmark className="h-[23px] w-auto" />
                  </a>
                  <button
                    ref={closeRef}
                    type="button"
                    aria-label="Close menu"
                    onClick={() => setOpen(false)}
                    className="flex size-11 items-center justify-center rounded-full text-white/85 hover:text-white"
                  >
                    <IconX size={22} stroke={1.6} aria-hidden="true" />
                  </button>
                </div>
                <nav
                  aria-label="Menu"
                  className="flex-1 overflow-y-auto px-4 pt-6 sm:px-7"
                >
                  <ul>
                    {items.map(([label, href], i) => (
                      <motion.li
                        key={href}
                        initial={reduce ? false : { opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{
                          delay: 0.04 * i,
                          duration: 0.3,
                          ease: [0.16, 1, 0.3, 1],
                        }}
                        className="border-b border-line"
                      >
                        <a
                          href={href}
                          onClick={() => setOpen(false)}
                          className="font-display block py-4 text-[28px] tracking-[-0.03em] no-underline"
                        >
                          {label}
                        </a>
                      </motion.li>
                    ))}
                  </ul>
                </nav>
                <div className="px-4 pb-8 pt-4 sm:px-7">
                  <a
                    href="#demo"
                    onClick={() => setOpen(false)}
                    className="btn btn-primary w-full"
                  >
                    Book a demo
                  </a>
                </div>
              </motion.div>
            )}
          </AnimatePresence>,
          document.body,
        )}
    </div>
  );
}
