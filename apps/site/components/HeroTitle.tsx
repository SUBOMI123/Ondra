/**
 * The hero headline resolves word by word out of a soft blur: the page's one orchestrated
 * load moment. Pure CSS (no JS needed), so it's visible at first paint for crawlers and
 * no-JS visitors; under reduced motion the words simply sit at rest.
 */
export default function HeroTitle({ text, className = "" }: { text: string; className?: string }) {
  const words = text.split(" ");
  return (
    <h1 className={className} aria-label={text}>
      {words.map((w, i) => (
        <span
          key={i}
          aria-hidden="true"
          className="inline-block whitespace-pre motion-safe:animate-word"
          style={{ animationDelay: `${150 + i * 90}ms` }}
        >
          {w}
          {i < words.length - 1 ? " " : ""}
        </span>
      ))}
    </h1>
  );
}
