/**
 * Ondra's mark: the speedometer from the logo, used wherever the product shows "Ondra did this".
 * Takes the current text colour, so badges and labels colour it.
 */
export function OndraMark({ className = "size-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={className}>
      <path d="M7.41 20.66A8.2 9.0 0 1 1 16.59 20.66" stroke="currentColor" strokeWidth={3} strokeLinecap="round" />
      <path d="M12 13.2L15.59 9.25" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" />
      <circle cx="12" cy="13.2" r="1.9" fill="currentColor" />
    </svg>
  )
}
