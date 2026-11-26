"""Connect a Twilio phone number to Ondra's voice agent through LiveKit (Step 5e). Safe to run again: each piece is
found by name and only created if missing.

    uv run python infra/telephony/connect_line.py --number +17073068599 --sip-uri sip:<project>.sip.livekit.cloud

What it sets up (from LiveKit's "Create and configure a Twilio SIP trunk" guide and Twilio's trunk API docs):

  Twilio  an Elastic SIP trunk ("Ondra voice", *.pstn.twilio.com) with call transfer enabled (VIP calls and warm
          transfers ring a person's mobile), an origination URI pointing at the LiveKit project's SIP URI, a
          credential list LiveKit uses to place calls out through the trunk, and the phone number on the trunk.
          Elastic SIP Trunking, not a TwiML Bin: LiveKit documents that the TwiML route supports neither transfers
          nor outbound calls.
  LiveKit an inbound trunk for the number, a dispatch rule that puts each caller in their own room and dispatches
          the `ondra-voice` agent, and an outbound trunk to Twilio for transfers.

Credentials: Twilio from TWILIO_API_KEY / TWILIO_API_SECRET (or TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN) when set;
otherwise none are sent (in Ondra's cloud build environment a network proxy adds them). LiveKit from LIVEKIT_URL,
LIVEKIT_API_KEY, LIVEKIT_API_SECRET. The SIP password it creates is written to the gitignored .env, never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import secrets
import string
from pathlib import Path

import aiohttp
import httpx
from livekit import api
from livekit.protocol.sip import (
    CreateSIPDispatchRuleRequest,
    CreateSIPInboundTrunkRequest,
    CreateSIPOutboundTrunkRequest,
    ListSIPDispatchRuleRequest,
    ListSIPInboundTrunkRequest,
    ListSIPOutboundTrunkRequest,
    SIPDispatchRule,
    SIPDispatchRuleIndividual,
    SIPDispatchRuleInfo,
    SIPInboundTrunkInfo,
    SIPOutboundTrunkInfo,
)

ENV = Path(__file__).resolve().parents[2] / ".env"
NAME = "Ondra voice"
AGENT = "ondra-voice"
SIP_USER = "ondra-livekit"


def env_file() -> dict[str, str]:
    if not ENV.exists():
        return {}
    return dict(line.split("=", 1) for line in ENV.read_text().splitlines() if "=" in line and not line.startswith("#"))


def set_env(key: str, value: str) -> None:
    text = ENV.read_text() if ENV.exists() else ""
    line = f"{key}={value}"
    text = re.sub(rf"^{key}=.*$", line, text, flags=re.M) if re.search(rf"^{key}=", text, re.M) else text.rstrip("\n") + f"\n{line}\n"
    ENV.write_text(text)


def strong_password() -> str:
    # Twilio SIP credentials: at least 12 characters, with upper case, lower case and a digit.
    alphabet = string.ascii_letters + string.digits
    while True:
        p = "".join(secrets.choice(alphabet) for _ in range(24))
        if any(c.isupper() for c in p) and any(c.islower() for c in p) and any(c.isdigit() for c in p):
            return p


class Twilio:
    def __init__(self) -> None:
        user = os.getenv("TWILIO_API_KEY") or os.getenv("TWILIO_ACCOUNT_SID")
        secret = os.getenv("TWILIO_API_SECRET") or os.getenv("TWILIO_AUTH_TOKEN")
        self.http = httpx.Client(auth=(user, secret) if user and secret else None, timeout=30)
        accounts = self.get("https://api.twilio.com/2010-04-01/Accounts.json")["accounts"]
        self.account = next(a["sid"] for a in accounts if a["status"] == "active")
        self.base = f"https://api.twilio.com/2010-04-01/Accounts/{self.account}"

    def get(self, url: str, **params) -> dict:
        r = self.http.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def post(self, url: str, **data) -> dict:
        r = self.http.post(url, data=data)
        if r.status_code >= 400:
            raise SystemExit(f"Twilio refused {url.split('.com')[1]}: {r.status_code} {r.text[:300]}")
        return r.json()


def twilio_setup(tw: Twilio, number: str, sip_uri: str | None, password: str) -> tuple[str, str]:
    """Sets up the Twilio side and returns the trunk's domain."""
    T = "https://trunking.twilio.com/v1/Trunks"
    trunk = next((t for t in tw.get(T, PageSize=50)["trunks"] if t["friendly_name"] == NAME), None)
    if trunk is None:
        domain = f"ondra-{secrets.token_hex(4)}.pstn.twilio.com"
        trunk = tw.post(T, FriendlyName=NAME, DomainName=domain, TransferMode="enable-all")
        print(f"twilio: created trunk {trunk['sid']} ({domain})")
    else:
        print(f"twilio: trunk exists {trunk['sid']} ({trunk['domain_name']})")
        if trunk.get("transfer_mode") != "enable-all":
            tw.post(f"{T}/{trunk['sid']}", TransferMode="enable-all")
            print("twilio: call transfer enabled")
    sid = trunk["sid"]

    if sip_uri:
        want = f"{sip_uri};transport=tcp"
        urls = tw.get(f"{T}/{sid}/OriginationUrls")["origination_urls"]
        if not any(u["sip_url"] == want for u in urls):
            tw.post(f"{T}/{sid}/OriginationUrls", FriendlyName="LiveKit SIP URI", SipUrl=want, Weight=1, Priority=1,
                    Enabled="true")
            print(f"twilio: origination -> {want}")
        else:
            print("twilio: origination already points at LiveKit")
    else:
        print("twilio: no --sip-uri given, so calls won't reach LiveKit yet (origination not set)")

    # The credential LiveKit uses to send calls out through the trunk (transfers).
    lists = tw.get(f"{tw.base}/SIP/CredentialLists.json")["credential_lists"]
    cl = next((c for c in lists if c["friendly_name"] == NAME), None)
    if cl is None:
        cl = tw.post(f"{tw.base}/SIP/CredentialLists.json", FriendlyName=NAME)
        tw.post(f"{tw.base}/SIP/CredentialLists/{cl['sid']}/Credentials.json", Username=SIP_USER, Password=password)
        print("twilio: created SIP credential for LiveKit")
    attached = tw.get(f"{T}/{sid}/CredentialLists")["credential_lists"]
    if not any(c["sid"] == cl["sid"] for c in attached):
        tw.post(f"{T}/{sid}/CredentialLists", CredentialListSid=cl["sid"])
        print("twilio: credential attached to trunk")

    nums = tw.get(f"{tw.base}/IncomingPhoneNumbers.json", PhoneNumber=number)["incoming_phone_numbers"]
    if not nums:
        raise SystemExit(f"twilio: {number} isn't on this account")
    n = nums[0]
    if n.get("trunk_sid") != sid:
        tw.post(f"{T}/{sid}/PhoneNumbers", PhoneNumberSid=n["sid"])
        print(f"twilio: {number} now on the trunk")
    else:
        print(f"twilio: {number} already on the trunk")
    return trunk["domain_name"]


async def livekit_setup(number: str, domain: str, password: str) -> str:
    # trust_env: use HTTPS_PROXY when one is set (aiohttp ignores it by default).
    session = aiohttp.ClientSession(trust_env=True)
    lk = api.LiveKitAPI(session=session)
    try:
        inbound = next((t for t in (await lk.sip.list_inbound_trunk(ListSIPInboundTrunkRequest())).items
                        if t.name == NAME), None)
        if inbound is None:
            inbound = await lk.sip.create_inbound_trunk(CreateSIPInboundTrunkRequest(
                trunk=SIPInboundTrunkInfo(name=NAME, numbers=[number], krisp_enabled=True)))
            print(f"livekit: created inbound trunk {inbound.sip_trunk_id}")
        else:
            print(f"livekit: inbound trunk exists {inbound.sip_trunk_id}")

        rules = (await lk.sip.list_dispatch_rule(ListSIPDispatchRuleRequest())).items
        if not any(r.name == NAME for r in rules):
            rule = await lk.sip.create_dispatch_rule(CreateSIPDispatchRuleRequest(dispatch_rule=SIPDispatchRuleInfo(
                name=NAME, trunk_ids=[inbound.sip_trunk_id],
                rule=SIPDispatchRule(dispatch_rule_individual=SIPDispatchRuleIndividual(room_prefix="call-")),
                room_config=api.RoomConfiguration(agents=[api.RoomAgentDispatch(agent_name=AGENT)]),
            )))
            print(f"livekit: created dispatch rule {rule.sip_dispatch_rule_id} -> agent {AGENT}")
        else:
            print("livekit: dispatch rule exists")

        outbound = next((t for t in (await lk.sip.list_outbound_trunk(ListSIPOutboundTrunkRequest())).items
                         if t.name == NAME), None)
        if outbound is None:
            outbound = await lk.sip.create_outbound_trunk(CreateSIPOutboundTrunkRequest(trunk=SIPOutboundTrunkInfo(
                name=NAME, address=domain, numbers=[number], auth_username=SIP_USER, auth_password=password)))
            print(f"livekit: created outbound trunk {outbound.sip_trunk_id}")
        else:
            print(f"livekit: outbound trunk exists {outbound.sip_trunk_id}")
        return outbound.sip_trunk_id
    finally:
        await lk.aclose()
        await session.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--number", required=True, help="The Twilio number, E.164, e.g. +17073068599")
    ap.add_argument("--sip-uri", help="The LiveKit project's SIP URI (Project settings), e.g. sip:abc123.sip.livekit.cloud")
    a = ap.parse_args()
    if a.sip_uri and not re.fullmatch(r"sip:[a-z0-9]+\.sip\.livekit\.cloud", a.sip_uri):
        raise SystemExit("--sip-uri should look like sip:abc123.sip.livekit.cloud")
    for k, v in env_file().items():
        os.environ.setdefault(k, v)
    password = os.getenv("TWILIO_SIP_PASSWORD") or strong_password()
    set_env("TWILIO_SIP_PASSWORD", password)  # gitignored; needed if the LiveKit outbound trunk is recreated

    domain = twilio_setup(Twilio(), a.number, a.sip_uri, password)
    trunk_id = asyncio.run(livekit_setup(a.number, domain, password))
    set_env("LIVEKIT_SIP_OUTBOUND_TRUNK", trunk_id)
    set_env("DEALER_PHONE", a.number)
    print("done: LIVEKIT_SIP_OUTBOUND_TRUNK and DEALER_PHONE written to .env")


if __name__ == "__main__":
    main()
