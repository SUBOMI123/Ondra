"""Which adapter handles each channel. A channel uses its mock until its feature flag is on, so the system runs with
no provider accounts. Mocks are module-level singletons so tests and the dev outbox can read what was "sent"."""

from __future__ import annotations

from functools import lru_cache

from ondra_core.channels.base import ChannelAdapter
from ondra_core.channels.mock import MockAdapter
from ondra_core.channels.postmark import PostmarkAdapter
from ondra_core.channels.twilio_sms import TwilioSmsAdapter
from ondra_core.channels.whatsapp import WhatsAppCloudAdapter

from ondra_api.config import get_settings

CHANNELS = ("whatsapp", "sms", "email")


@lru_cache
def mock(channel: str) -> MockAdapter:
    return MockAdapter(channel, secret=get_settings().mock_webhook_secret)


@lru_cache
def real(channel: str) -> ChannelAdapter | None:
    s = get_settings()
    if channel == "whatsapp" and s.feature_whatsapp:
        return WhatsAppCloudAdapter(access_token=s.whatsapp_token, app_secret=s.whatsapp_app_secret,
                                    verify_token=s.whatsapp_verify_token, phone_number_id=s.whatsapp_phone_number_id,
                                    api_version=s.whatsapp_api_version)
    if channel == "sms" and s.feature_sms:
        return TwilioSmsAdapter(account_sid=s.twilio_account_sid, auth_token=s.twilio_auth_token,
                                messaging_service_sid=s.twilio_messaging_service_sid or None)
    if channel == "email" and s.feature_email:
        return PostmarkAdapter(server_token=s.postmark_server_token, webhook_user=s.postmark_inbound_user,
                               webhook_password=s.postmark_inbound_password)
    return None


def adapter_for(channel: str, provider: str) -> ChannelAdapter:
    """The adapter that sends on `channel` for an address registered with `provider`."""
    if provider == "mock":
        return mock(channel)
    a = real(channel)
    if a is None or a.provider != provider:
        raise LookupError(f"{provider} is not enabled for {channel}")
    return a
