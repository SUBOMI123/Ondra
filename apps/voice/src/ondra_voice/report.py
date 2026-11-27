"""Latency report for real calls (Step 5e): where each turn's wait goes.

    python -m ondra_voice.report            the last 5 calls Ondra answered
    python -m ondra_voice.report --last 10

Per call: turns, average and 90th percentile from the caller stopping to Ondra's voice starting (plan §6.4 target:
under 1 s on average), and that wait split into its parts as the call record stores them: deciding the caller has
finished (end of turn), the model's first word, the voice's first sound, and tools. "Unaccounted" is the average
minus the parts: time no stage owns (network, queueing, the pipeline between stages). That's the number to chase
when turns run at 3.5 s and the parts add up to far less.
"""

from __future__ import annotations

import argparse
import asyncio


def breakdown(summary: dict) -> dict:
    parts = {k: summary.get(f"avg_{k}_ms") for k in ("end_of_turn", "llm_ttft", "tts_ttfb", "tool")}
    known = sum(v for v in parts.values() if v)
    avg = summary.get("avg_ms")
    return {**parts, "avg": avg, "p90": summary.get("p90_ms"), "turns": summary.get("turns"),
            "unaccounted": (avg - known) if avg is not None else None}


async def _calls(last: int) -> list:
    from ondra_api.db import no_tenant_session
    from sqlalchemy import text

    async with no_tenant_session() as db:  # a developer tool, run by hand: reads across dealers
        return (await db.execute(text(
            "SELECT id, started_at, metrics->'summary' AS s FROM calls WHERE handled_by IN ('ai', 'staff') "
            "AND metrics ? 'summary' AND (metrics->'summary'->>'turns')::int > 0 ORDER BY started_at DESC LIMIT :n"),
            {"n": last})).all()


def main() -> None:
    p = argparse.ArgumentParser(description="Where the wait goes on recent real calls.")
    p.add_argument("--last", type=int, default=5)
    rows = asyncio.run(_calls(p.parse_args().last))
    if not rows:
        raise SystemExit("No answered calls with timings yet.")
    ms = lambda v: f"{v / 1000:.2f} s" if isinstance(v, (int, float)) else "-"
    print(f"{'call':10} {'turns':>5} {'average':>9} {'p90':>9} {'end of turn':>12} {'model':>9} {'voice':>9} {'tools':>9} {'unaccounted':>12}")
    for r in rows:
        b = breakdown(r.s or {})
        print(f"{str(r.id)[:8]:10} {b['turns'] or 0:>5} {ms(b['avg']):>9} {ms(b['p90']):>9} {ms(b['end_of_turn']):>12} "
              f"{ms(b['llm_ttft']):>9} {ms(b['tts_ttfb']):>9} {ms(b['tool']):>9} {ms(b['unaccounted']):>12}")
    print("\nTarget: under 1 s on average (plan §6.4).")


if __name__ == "__main__":
    main()
