import Wordmark from "@/components/Wordmark";
import SiteFooter from "@/components/SiteFooter";

/** A plain, readable page for legal text: the wordmark home, the title and date, the sections, the footer. */
export default function LegalPage({ title, updated, intro, children }: { title: string; updated: string; intro: React.ReactNode; children: React.ReactNode }) {
  return (
    <>
      <header className="on-dark border-b border-line bg-bg">
        <div className="mx-auto flex w-full max-w-(--container-page) items-center justify-between px-4 py-5 text-white sm:px-7">
          <a href="/" aria-label="Ondra home" className="flex items-center no-underline"><Wordmark className="h-[23px] w-auto" /></a>
          <a href="/#demo" className="btn btn-quiet min-h-11 px-4">Book a demo</a>
        </div>
      </header>
      <main className="bg-bg py-16 sm:py-24">
        <article className="legal mx-auto w-full max-w-[72ch] px-4 sm:px-7">
          <h1 className="font-display text-h2">{title}</h1>
          <p className="text-small mt-3 text-muted-foreground">Last updated {updated}</p>
          <div className="text-lead mt-8 text-fg-2 [&_a]:text-fg [&_a]:underline [&_a]:underline-offset-4">{intro}</div>
          <div className="mt-12 flex flex-col gap-10">{children}</div>
        </article>
      </main>
      <SiteFooter />
    </>
  );
}

export function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3 text-fg-2 [&_li]:ml-5 [&_li]:list-disc [&_li]:pl-1 [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-2 [&_a]:text-fg [&_a]:underline [&_a]:underline-offset-4 [&_strong]:font-medium [&_strong]:text-fg">
      <h2 id={id} className="text-h4 text-fg">{title}</h2>
      {children}
    </section>
  );
}
