import type { Metadata } from "next";

import LegalPage, { Section } from "@/components/LegalPage";
import { BRAND_NAME, CONTACT_EMAIL, TEXT_NUMBER } from "@/lib/config";

export const metadata: Metadata = {
  title: "Terms of service: Ondra",
  description: "The terms for using Ondra and this website.",
};

// Written to match how Ondra works today. Before relying on it: have counsel review it, and add the company's legal
// name, address and the governing law and venue (TODO: legal entity, address, governing law, dispute resolution).
// A dealership's signed agreement or order form takes precedence (said in "Your agreement" below).
export default function TermsPage() {
  const mail = <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>;
  return (
    <LegalPage
      title="Terms of service"
      updated="November 28, 2026"
      intro={<p>These terms cover using Ondra, the service that answers calls and messages for car dealerships, and this website. By using either, you agree to them. Questions: {mail}.</p>}
    >
      <Section id="agreement" title="Your agreement">
        <p>A dealership that signs an agreement or order form with us uses Ondra under that document. Where it and these terms differ, the signed document wins. Fees, plan and term are set there.</p>
      </Section>

      <Section id="service" title="What Ondra does">
        <p>Ondra answers a dealership&apos;s calls, texts, WhatsApp and email, answers questions from the dealership&apos;s own information, books appointments into the dealership&apos;s calendar, and passes conversations to the dealership&apos;s staff when a person is needed. It doesn&apos;t answer clients the dealership marks as VIPs; their calls and messages go to a person.</p>
      </Section>

      <Section id="ai" title="AI can be wrong">
        <ul>
          <li>Ondra&apos;s replies are written by an AI model. It can misunderstand a customer or make mistakes.</li>
          <li>Ondra won&apos;t agree a final price, a discount or a delivery date unless the dealership&apos;s settings allow it. Any deal, price or commitment to a customer is the dealership&apos;s to make and honour.</li>
          <li>The dealership is responsible for reviewing how Ondra answers (draft mode lets staff approve replies before they&apos;re sent) and for the information it gives Ondra, such as stock, prices and opening hours.</li>
        </ul>
      </Section>

      <Section id="dealer" title="The dealership&apos;s responsibilities">
        <ul>
          <li>Have the right to contact the customers Ondra messages and calls for it, including any consent the law requires for automated texts and calls. Ondra doesn&apos;t send automated messages or make automated calls without recorded consent, and it honours opt-outs on every channel.</li>
          <li>Tell customers they&apos;re talking to an AI where the law requires it (Ondra has a setting for this) and, where calls are recorded, that they are.</li>
          <li>Keep staff sign-ins secure, give access only to its own staff, and remove people who leave.</li>
          <li>Follow the laws that apply to its business and its customers, including privacy, consumer and advertising laws.</li>
        </ul>
      </Section>

      <Section id="use" title="Acceptable use">
        <p>Don&apos;t use Ondra to send spam or messages people haven&apos;t agreed to, to deceive anyone, to break the law or someone else&apos;s rights, or to try to get into another dealership&apos;s data or interfere with the service.</p>
      </Section>

      <Section id="data" title="Data">
        <p>A dealership owns its data and its customers&apos; data. We use it only to provide Ondra to that dealership, as described in our <a href="/privacy">privacy policy</a>. The dealership can ask us to export or delete it.</p>
      </Section>

      <Section id="third" title="Phone and messaging networks">
        <p>Ondra relies on carriers and platforms such as Twilio, WhatsApp and email providers. Their rules apply to messages sent through them, and we can&apos;t guarantee their delivery or availability.</p>
      </Section>

      <Section id="texts" title="SMS terms">
        <p>{BRAND_NAME} (Ondra) sends text messages from {TEXT_NUMBER}, and for a dealership from that dealership&apos;s own number, about a person&apos;s own enquiry: replies to their questions, details of cars they asked about, appointment confirmations, reminders and changes, a text after a missed call, and one-time codes they ask for. No marketing messages are sent. Texts go only to people who texted first or agreed to texts, for example by saying yes on a call. Agreeing is never a condition of buying anything.</p>
        <ul>
          <li>Message frequency varies with the conversation.</li>
          <li>Message and data rates may apply.</li>
          <li>Reply STOP to stop all texts. You&apos;ll get one message confirming it, and nothing after. Reply START to opt back in.</li>
          <li>Reply HELP for help, call {TEXT_NUMBER}, or email {mail}.</li>
          <li>Carriers are not liable for delayed or undelivered messages.</li>
        </ul>
        <p id="verbal-consent"><strong>How callers agree to texts.</strong> When a caller asks about cars or a booking, Ondra asks: &ldquo;Can I text you the details? Message and data rates may apply, and you can reply STOP at any time.&rdquo; It sends a text only after the caller says yes. Their answer, the time and the call are stored as their consent, and the first text confirms it, with how to get help or stop.</p>
        <p>How mobile numbers are handled is in our <a href="/privacy#texts">privacy policy</a>.</p>
      </Section>

      <Section id="ours" title="Ours">
        <p>Ondra, its software and its content (other than the dealership&apos;s data) belong to us. The dealership may use Ondra while its agreement is in place.</p>
      </Section>

      <Section id="warranty" title="Availability and warranties">
        <p>We work to keep Ondra running and answering correctly, but it&apos;s provided as it is and as available, without warranties beyond those the law requires or a signed agreement gives.</p>
      </Section>

      <Section id="liability" title="Limits on liability">
        <p>To the extent the law allows, we aren&apos;t liable for indirect or consequential losses, such as lost sales or profits, and our total liability is limited to what the dealership paid us for Ondra in the twelve months before the claim.</p>
      </Section>

      <Section id="ending" title="Ending">
        <p>A dealership can stop using Ondra as its agreement allows. We may suspend access that breaks these terms or puts others at risk, and we&apos;ll tell the dealership why.</p>
      </Section>

      <Section id="changes" title="Changes and contact">
        <p>If we change these terms, we&apos;ll update the date at the top and tell dealerships directly about anything significant. Questions: {mail}.</p>
      </Section>
    </LegalPage>
  );
}
