"use client";

import { useState } from "react";
import { CONTACT_EMAIL, DEMO_FORM_ENDPOINT } from "@/lib/config";

type Status = "idle" | "sending" | "sent" | "error";

const CHANNELS = ["Phone", "WhatsApp", "SMS", "Email", "Instagram"];

export default function DemoForm() {
  const [status, setStatus] = useState<Status>("idle");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    if (fd.get("company_website")) return; // honeypot: bots fill hidden fields

    const data = {
      name: String(fd.get("name") ?? ""),
      dealership: String(fd.get("dealership") ?? ""),
      email: String(fd.get("email") ?? ""),
      phone: String(fd.get("phone") ?? ""),
      city: String(fd.get("city") ?? ""),
      channels: fd.getAll("channels").map(String),
      dms: String(fd.get("dms") ?? ""),
      notes: String(fd.get("notes") ?? ""),
      source: "landing",
    };

    // No endpoint configured yet: hand off to the visitor's email client so no lead is lost.
    if (!DEMO_FORM_ENDPOINT) {
      const body = Object.entries(data)
        .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
        .join("\n");
      window.location.href = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(
        `Ondra demo: ${data.dealership || data.name}`,
      )}&body=${encodeURIComponent(body)}`;
      setStatus("sent");
      return;
    }

    setStatus("sending");
    try {
      const res = await fetch(DEMO_FORM_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(String(res.status));
      setStatus("sent");
      form.reset();
    } catch {
      setStatus("error");
    }
  }

  if (status === "sent") {
    return (
      <div role="status" className="rounded-card border border-line bg-surface p-8">
        <p className="font-display text-2xl font-bold">Thanks. We&apos;ll be in touch within one business day.</p>
        <p className="mt-3 text-fg-2">
          We&apos;ll set up a call to look at how your calls and messages come in today, then show Ondra answering them.
        </p>
      </div>
    );
  }

  const input =
    "mt-1.5 block w-full rounded-control border border-line bg-surface px-3.5 py-3 text-[15px] text-fg placeholder:text-muted-foreground/70 focus:border-fg/70 focus:outline-none";
  const label = "block text-sm font-semibold text-fg";

  return (
    <form onSubmit={onSubmit} className="rounded-card border border-line bg-surface p-6 sm:p-8" noValidate={false}>
      <div className="grid gap-5 sm:grid-cols-2">
        <label className={label}>
          Your name
          <input name="name" required autoComplete="name" className={input} />
        </label>
        <label className={label}>
          Dealership
          <input name="dealership" required autoComplete="organization" className={input} />
        </label>
        <label className={label}>
          Work email
          <input name="email" type="email" required autoComplete="email" className={input} />
        </label>
        <label className={label}>
          Phone
          <input name="phone" type="tel" autoComplete="tel" className={input} />
        </label>
        <label className={`${label} sm:col-span-2`}>
          City and state
          <input name="city" placeholder="Dallas, TX" className={input} />
        </label>
      </div>

      <fieldset className="mt-6">
        <legend className={label}>Where do buyers reach you today?</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {CHANNELS.map((c) => (
            <label
              key={c}
              className="flex cursor-pointer items-center gap-2 rounded-full border border-line px-3.5 py-2 text-sm has-[:checked]:border-brand has-[:checked]:bg-brand has-[:checked]:text-white"
            >
              <input type="checkbox" name="channels" value={c} className="sr-only" />
              {c}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="mt-6">
        <legend className={label}>Do you use a DMS or CRM?</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {["Yes", "No", "Not sure"].map((c) => (
            <label
              key={c}
              className="flex cursor-pointer items-center gap-2 rounded-full border border-line px-3.5 py-2 text-sm has-[:checked]:border-brand has-[:checked]:bg-brand has-[:checked]:text-white"
            >
              <input type="radio" name="dms" value={c} className="sr-only" />
              {c}
            </label>
          ))}
        </div>
      </fieldset>

      <label className={`${label} mt-6`}>
        Anything we should know? <span className="font-normal text-muted-foreground">(optional)</span>
        <textarea
          name="notes"
          rows={3}
          placeholder="e.g. We miss calls after 7pm and web leads sit until morning."
          className={input}
        />
      </label>

      {/* Honeypot, hidden from people and screen readers */}
      <div aria-hidden="true" className="absolute -left-[9999px]">
        <input name="company_website" tabIndex={-1} autoComplete="off" />
      </div>

      <div className="mt-7 flex flex-wrap items-center gap-4">
        <button type="submit" className="btn btn-primary" disabled={status === "sending"}>
          {status === "sending" ? "Sending…" : "Book a demo"}
        </button>
        <p className="text-sm text-muted-foreground">30 minutes. No sales script, just your calls and messages.</p>
      </div>
      {status === "error" && (
        <p role="alert" className="mt-4 text-sm text-vip">
          That didn&apos;t send. Email us at{" "}
          <a className="underline" href={`mailto:${CONTACT_EMAIL}`}>
            {CONTACT_EMAIL}
          </a>{" "}
          and we&apos;ll reply the same day.
        </p>
      )}
    </form>
  );
}
