"""Fetching a dealer's inventory feed from a URL they gave us, on a schedule.

A URL typed into a settings form is untrusted: without checks, the server could be pointed at its own network
(cloud metadata, internal services). So: https only, no credentials in the URL, the host must resolve only to
public addresses, no redirects are followed, and the download is capped at 5 MB.
Known gap: the address is checked and then connected to by name, so a host that changes its DNS between the two
(DNS rebinding) isn't stopped here. Close it at hosting by sending these fetches through an egress proxy that
refuses private ranges. Recorded in docs/DECISIONS.md.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from ondra_core.inventory_feed import MAX_BYTES

from ondra_api.db import tenant_session
from ondra_api.services.inventory import feed_integration, import_inventory
from ondra_api.services.jobs import enqueue

log = logging.getLogger("ondra.feed")
SCHEDULES = (0, 1, 6, 24)  # hours between fetches; 0 is off


class FeedError(Exception):
    """Why the feed couldn't be fetched, in words a dealer can act on."""


def check_url(url: str) -> str:
    """The URL if it may be fetched, else FeedError. Doesn't resolve DNS (see `_check_host`)."""
    parts = urlsplit((url or "").strip())
    if parts.scheme != "https":
        raise FeedError("The feed address must start with https://")
    if not parts.hostname or parts.username or parts.password:
        raise FeedError("Use a plain https address, without a username or password in it.")
    if parts.port not in (None, 443):
        raise FeedError("The feed address must use the standard https port.")
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")) or "." not in host:
        raise FeedError("That address isn't on the public internet.")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise FeedError("That address isn't on the public internet.")
    except ValueError:
        pass  # a name, not an IP: resolved and checked at fetch time
    return parts.geturl()


async def _check_host(host: str) -> None:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise FeedError("That address couldn't be found.") from None
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise FeedError("That address isn't on the public internet.")


async def fetch(url: str) -> str:
    url = check_url(url)
    await _check_host(urlsplit(url).hostname)
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=True) as client, client.stream("GET", url) as r:
            if r.status_code in (301, 302, 303, 307, 308):
                raise FeedError("The feed address redirects somewhere else. Use the final address.")
            if r.status_code != 200:
                raise FeedError(f"The feed answered with an error ({r.status_code}).")
            chunks, size = [], 0
            async for chunk in r.aiter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise FeedError("The feed is larger than 5 MB.")
                chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise FeedError(f"The feed couldn't be reached ({type(exc).__name__}).") from None
    return b"".join(chunks).decode("utf-8", errors="replace")


fetcher = fetch  # tests replace this


def schedule_next(db, hours: int) -> None:
    if hours in SCHEDULES and hours > 0:
        enqueue(db, "inventory_fetch", {}, run_at=datetime.now(UTC) + timedelta(hours=hours))


async def run(tenant_id: uuid.UUID, payload: dict) -> str:
    """The job: fetch, import as the whole lot, line up the next fetch. A feed that fails keeps its schedule."""
    async with tenant_session(tenant_id) as db:
        integ = await feed_integration(db)
        cfg = dict(integ.config or {})
        url, hours = cfg.get("url"), int(cfg.get("every_hours") or 0)
        if not url or hours == 0:
            return "skipped: no scheduled feed"
        if payload.get("for") and payload["for"] != cfg.get("schedule_id"):
            return "skipped: schedule changed"  # an older schedule's job; the new one has its own
    try:
        text = await fetcher(url)
    except FeedError as e:
        async with tenant_session(tenant_id) as db:
            integ = await feed_integration(db)
            integ.status = "error"
            integ.config = {**(integ.config or {}), "last": {"ok": False, "error": str(e), "at": datetime.now(UTC).isoformat(), "source": "feed"}}
            enqueue(db, "inventory_fetch", {"for": cfg.get("schedule_id")}, run_at=datetime.now(UTC) + timedelta(hours=hours))
        return f"failed: {e}"
    async with tenant_session(tenant_id) as db:
        out = await import_inventory(db, text, urlsplit(url).path.rsplit("/", 1)[-1], source="feed", whole_lot=True)
        enqueue(db, "inventory_fetch", {"for": cfg.get("schedule_id")}, run_at=datetime.now(UTC) + timedelta(hours=hours))
    return "imported" if out["ok"] else f"failed: {out['error']}"
