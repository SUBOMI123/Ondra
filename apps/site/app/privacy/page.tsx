import type { Metadata } from "next";

import LegalPage, { Section } from "@/components/LegalPage";
import { CONTACT_EMAIL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Privacy policy: Ondra",
  description: "What Ondra collects, why, who processes it, and how to have it corrected or deleted.",
};

// Written to match how Ondra works today (the code and docs/DECISIONS.md). Before relying on it: have counsel review it,
// and add the company's legal name and address (TODO: legal entity, registered address).
export default function PrivacyPage() {
  const mail = <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>;
  return (
    <LegalPage
      title="Privacy policy"
      updated="November 28, 2026"
      intro={<p>Ondra answers calls and messages for car dealerships. This page explains what information we handle, why, who helps us handle it, and what you can ask us to do with it. If anything here is unclear, email {mail}.</p>}
    >
      <Section id="who" title="Two kinds of information">
        <p>
          <strong>Our own:</strong> what people send us directly, such as the demo request form on this website, and the accounts of the
          dealership staff who use Ondra.
        </p>
        <p>
          <strong>Our dealerships&apos;:</strong> the conversations, calls and bookings of a dealership&apos;s customers. We handle that on the
          dealership&apos;s behalf and only to provide Ondra to them. The dealership decides how it&apos;s used; if you&apos;re a dealership&apos;s
          customer, the dealership is the first place to ask about your information, and we help them answer.
        </p>
      </Section>

      <Section id="site" title="This website">
        <ul>
          <li>No analytics, advertising trackers or cookies.</li>
          <li>
            The demo form asks for your name, dealership, email, and optionally your phone number, city and the channels buyers use to reach
            you. It&apos;s delivered to us by email through Formspree. We use it to reply to you and to arrange a demo, nothing else.
          </li>
          <li>The site is hosted by Cloudflare, which keeps standard request logs (such as IP addresses) to run and protect it.</li>
        </ul>
      </Section>

      <Section id="product" title="What Ondra handles for a dealership">
        <ul>
          <li>Customers&apos; names, phone numbers, email addresses and messaging handles.</li>
          <li>Messages by text, WhatsApp and email, and phone calls, including transcripts and summaries of calls. Calls are recorded only where the dealership has switched recording on and the caller is told.</li>
          <li>What a customer is looking for (a car, a service, a budget), their appointments, and their consent choices, including opt-outs.</li>
          <li>Dealership staff accounts: name, work email, role and, if they add it, a mobile number.</li>
        </ul>
      </Section>

      <Section id="use" title="How it&apos;s used">
        <ul>
          <li>To answer customers on the dealership&apos;s behalf, book appointments, and pass conversations to the right person at the dealership.</li>
          <li>To send the confirmations and reminders a customer agreed to. When anyone replies STOP, or otherwise opts out, Ondra stops messaging them on every channel.</li>
          <li>To show the dealership how its customers were looked after, and to improve how Ondra answers that dealership.</li>
        </ul>
        <p>We don&apos;t sell personal information, and we don&apos;t use a dealership&apos;s data to train AI models.</p>
      </Section>

      <Section id="processors" title="Who helps us run Ondra">
        <p>These companies process information for us, only to provide their part of the service:</p>
        <ul>
          <li>Fly.io (application hosting) and Supabase (database), in the United States.</li>
          <li>Cloudflare (website hosting and network) and Clerk (staff sign-in).</li>
          <li>Anthropic (the AI model that writes Ondra&apos;s replies) and Voyage AI (searching a dealership&apos;s own answers).</li>
          <li>LiveKit and its speech partners (phone calls, speech recognition and Ondra&apos;s voice), and Twilio (phone numbers and text messages).</li>
          <li>Meta (WhatsApp messages) and Postmark (email).</li>
          <li>Formspree (this website&apos;s demo form).</li>
        </ul>
      </Section>

      <Section id="security" title="How it&apos;s kept safe">
        <ul>
          <li>Each dealership&apos;s data is kept separate from every other dealership&apos;s, enforced in the database itself.</li>
          <li>Information is encrypted in transit, and our database provider encrypts it at rest.</li>
          <li>Staff sign in individually, and administrators use two-step sign-in.</li>
        </ul>
      </Section>

      <Section id="choices" title="Your choices">
        <ul>
          <li>Reply STOP to any text to stop all messages from that dealership through Ondra.</li>
          <li>Ask to see, correct or delete your information. A dealership&apos;s customer can ask the dealership, or email us at {mail} and we&apos;ll work with the dealership to do it.</li>
          <li>Depending on where you live (for example California), you may have further rights over your information. We honour them, and won&apos;t treat you differently for using them.</li>
        </ul>
      </Section>

      <Section id="keep" title="How long we keep it">
        <p>We keep a dealership&apos;s information while the dealership uses Ondra, and delete it when the dealership asks or stops using Ondra, unless the law requires us to keep something longer. Demo requests are kept as long as we&apos;re in touch about a demo.</p>
      </Section>

      <Section id="children" title="Children">
        <p>Ondra is for businesses and their adult customers. We don&apos;t knowingly collect information from children.</p>
      </Section>

      <Section id="changes" title="Changes and contact">
        <p>If we change this policy, we&apos;ll update the date at the top, and tell dealerships directly about anything significant. Questions or requests: {mail}.</p>
      </Section>
    </LegalPage>
  );
}
