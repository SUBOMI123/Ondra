/**
 * How a VIP looks, the same as in the app (apps/web/components/vip.tsx): a small "VIP" tag in ink, and a ring around
 * their initials. No crown and no red (founder, 2026-11-27): red means overdue and nothing else.
 */

export function VipTag({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex h-[18px] shrink-0 items-center rounded-[4px] border border-vip/50 px-1 text-[11px] font-semibold leading-none text-vip ${className}`}>
      VIP
    </span>
  );
}

export function VipInitials({ name, className = "" }: { name: string; className?: string }) {
  const parts = name.split(/\s+/).filter(Boolean);
  const letters = ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
  return (
    <span aria-hidden="true" className={`flex items-center justify-center rounded-full bg-bg font-medium text-fg ring-[1.5px] ring-vip ring-offset-2 ring-offset-surface ${className}`}>
      {letters}
    </span>
  );
}
