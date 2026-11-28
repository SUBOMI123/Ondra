"use client"

/**
 * Help. One job: understand how Ondra behaves and where things are, and reach us when that isn't enough.
 * Plain sections, no cards: how Ondra answers and when it hands over, where things live, shortcuts, and who to email.
 */

import { IconMail, IconSearch } from "@tabler/icons-react"
import Link from "next/link"

import { SiteHeader } from "@/components/dashboard/site-header"
import { OndraMark } from "@/components/ondra-mark"
import { useShell } from "@/components/shell/shell"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import { VipTag } from "@/components/vip"

const SCREENS: [string, string, string][] = [
  ["Today", "/", "What needs someone now, today's bookings, and how the week is going."],
  ["Inbox", "/inbox", "Every customer conversation, on every channel, in one thread per client. Approve Ondra's drafts here."],
  ["Calls", "/calls", "Who needs a call back, and what happened on every call."],
  ["Calendar", "/calendar", "Test drives and service, by person and by bay."],
  ["Clients", "/clients", "Everyone who's been in touch, their deal, and who looks after them."],
  ["Deals", "/deals", "Every buyer by stage, from new to won. Drag a card to move it."],
  ["Tasks", "/tasks", "Follow-ups for people: yours, or everyone's on a board."],
  ["Inventory", "/inventory", "What's on the lot, how long it's been there, and who's asking about it."],
]

export default function HelpPage() {
  const { openSearch, openCompose } = useShell()
  return (
    <>
      <SiteHeader title="Help" />
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 px-4 py-8 lg:px-6">
        <section aria-labelledby="ondra" className="flex flex-col gap-3">
          <h2 id="ondra" className="text-xl font-normal tracking-tight">How Ondra works</h2>
          <p className="text-pretty text-muted-foreground">
            Ondra answers your calls, texts, WhatsApp and email the moment they come in, day or night. It finds the car,
            books the test drive or the service, and passes the conversation to the right person on your team when a
            person is needed.
          </p>
          <ul className="flex flex-col gap-2.5 text-sm">
            <li className="flex gap-2"><OndraMark className="mt-0.5 size-4 shrink-0 text-ai" /><span><span className="text-ai">Blue</span> always means Ondra did it: a reply it sent, a draft it wrote, a booking it made.</span></li>
            <li className="flex gap-2"><span className="mt-0.5 shrink-0"><VipTag /></span><span>VIPs never hear from Ondra. Their calls ring their person directly, and only people can write to them.</span></li>
            <li className="pl-6">Ondra never agrees a final price, a discount or a delivery date unless your settings allow it. It passes those to a person.</li>
            <li className="pl-6">Anyone who replies STOP gets nothing more from you, on any channel.</li>
          </ul>
        </section>

        <section aria-labelledby="where" className="flex flex-col gap-3">
          <h2 id="where" className="text-xl font-normal tracking-tight">Where things are</h2>
          <dl className="divide-y border-y">
            {SCREENS.map(([name, href, what]) => (
              <div key={name} className="grid gap-1 py-3 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-4">
                <dt><Link href={href} className="font-medium underline-offset-4 hover:underline">{name}</Link></dt>
                <dd className="text-sm text-muted-foreground">{what}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section aria-labelledby="fast" className="flex flex-col gap-3">
          <h2 id="fast" className="text-xl font-normal tracking-tight">Getting around faster</h2>
          <div className="flex flex-col gap-3 text-sm sm:flex-row sm:flex-wrap sm:items-center">
            <Button variant="outline" size="sm" className="self-start" onClick={openSearch}><IconSearch /> Search</Button>
            <span className="text-muted-foreground">Or press <Kbd>⌘</Kbd> <Kbd>K</Kbd> (<Kbd>Ctrl</Kbd> <Kbd>K</Kbd> on Windows) anywhere. Find a client by name or any part of their number, a car by model or stock number, or a conversation by what was said.</span>
          </div>
          <div className="flex flex-col gap-3 text-sm sm:flex-row sm:flex-wrap sm:items-center">
            <Button variant="outline" size="sm" className="self-start" onClick={() => openCompose()}>New message</Button>
            <span className="text-muted-foreground">Write to any client first, on WhatsApp, by text or by email.</span>
          </div>
        </section>

        <section aria-labelledby="contact" className="flex flex-col gap-3">
          <h2 id="contact" className="text-xl font-normal tracking-tight">Still stuck?</h2>
          <p className="text-pretty text-muted-foreground">Email us and a person will get back to you. Say which screen you were on and what you expected to happen.</p>
          <Button asChild className="self-start"><a href="mailto:hello@useondra.com?subject=Ondra%20help"><IconMail /> hello@useondra.com</a></Button>
        </section>
      </div>
    </>
  )
}
