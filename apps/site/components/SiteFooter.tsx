import Wordmark from "@/components/Wordmark";
import { NAV_LINKS } from "@/components/navLinks";
import { CONTACT_EMAIL, SIGN_IN_URL, TEXT_NUMBER } from "@/lib/config";

/** The site footer, on the homepage and the legal pages. Section links are "/#..." so they work from any page. */
export default function SiteFooter() {
  const col = "flex flex-col gap-2.5";
  const link = "text-small w-fit text-white/65 no-underline hover:text-white";
  const head = "text-small font-medium text-white";
  return (
    <footer className="on-dark bg-night text-white/65">
      <div className="mx-auto grid w-full max-w-(--container-page) grid-cols-2 gap-x-8 gap-y-12 px-4 py-16 sm:px-7 md:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))]">
        <div className="col-span-2 flex flex-col items-start gap-5 md:col-span-1">
          <a href="/" aria-label="Ondra home" className="flex items-center text-white no-underline">
            <Wordmark className="h-[23px] w-auto" />
          </a>
          <p className="text-small max-w-[34ch]">AI staff for car dealerships: answers every call, text, WhatsApp and email, books the test drive, and hands the rest to your team.</p>
          <a href="/#demo" className="btn btn-primary min-h-11 px-4">Book a demo</a>
          {/* Where people find Ondra's own line. Carriers check that the number is published with its texting terms. */}
          <div id="try" className="flex max-w-[40ch] flex-col gap-1.5">
            <p className="text-small text-white">
              Hear Ondra answer: call or text <a href={`tel:+1${TEXT_NUMBER.replace(/\D/g, "")}`} className="text-white tabular-nums">{TEXT_NUMBER}</a>
            </p>
            <p className="text-micro text-white/50">
              Ondra texts only if you text first or say yes on the call, and only about your enquiry. Message frequency varies.
              Message and data rates may apply. Reply HELP for help, STOP to opt out. See our <a href="/terms#texts" className="text-white/70">SMS terms</a> and <a href="/privacy#texts" className="text-white/70">privacy policy</a>.
            </p>
          </div>
        </div>
        <nav aria-label="Product" className={col}>
          <p className={head}>Product</p>
          {NAV_LINKS.map(([label, href]) => (
            <a key={href} href={`/${href}`} className={link}>{label}</a>
          ))}
        </nav>
        <nav aria-label="Company" className={col}>
          <p className={head}>Company</p>
          <a href={SIGN_IN_URL} className={link}>Sign in</a>
          <a href="/#demo" className={link}>Book a demo</a>
          <a href={`mailto:${CONTACT_EMAIL}`} className={link}>{CONTACT_EMAIL}</a>
        </nav>
        <nav aria-label="Legal" className={col}>
          <p className={head}>Legal</p>
          <a href="/privacy" className={link}>Privacy policy</a>
          <a href="/terms" className={link}>Terms of service</a>
        </nav>
      </div>
      <div className="border-t border-white/10">
        <div className="mx-auto flex w-full max-w-(--container-page) flex-col gap-3 px-4 py-6 sm:flex-row sm:items-start sm:justify-between sm:px-7">
          <p className="text-micro shrink-0">© {new Date().getFullYear()} Ondra</p>
          {/* The licences require these credits (design/3d/README.md). */}
          <p className="text-micro max-w-[80ch] text-white/40 sm:text-right">
            3D car models from Blend Swap: Audi A8 by 50Groszy (CC BY-SA 3.0), BMW M4 F82 (#81957, CC BY 3.0), Lamborghini Urus
            2019 (#92440, CC BY-NC 3.0), 1968 Mustang GT Fastback (#82339, CC0). Badges and logos removed, paint changed.
          </p>
        </div>
      </div>
    </footer>
  );
}
