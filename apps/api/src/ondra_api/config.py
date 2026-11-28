from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from the environment (and a repo-root .env in development). See .env.example."""

    model_config = SettingsConfigDict(env_file=("../../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+asyncpg://ondra_app:ondra_app_dev@localhost:5432/ondra"
    migrations_database_url: str = "postgresql+asyncpg://ondra_owner:ondra_owner_dev@localhost:5432/ondra"
    jwt_secret: str = "dev-only-change-me-dev-only-change-me"
    # Signs customers' booking links (/b?t=...). Empty locally (the JWT secret is used); required on a public site.
    booking_link_secret: str = ""
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    app_base_url: str = "http://localhost:3001"
    # The API's public URL as providers call it. Twilio signs the exact URL, so this must match what Twilio sees.
    public_api_url: str = "http://localhost:8000"

    # --- Sign-in. "local": Ondra's own email and password (development, tests, no accounts needed). "clerk": Clerk
    # (staging and production). Roles, permissions and tenant isolation are Ondra's either way.
    auth_provider: str = "local"
    clerk_secret_key: str = ""
    clerk_api_base: str = "https://api.clerk.com"
    clerk_jwt_key: str = ""  # optional PEM public key (Dashboard > API keys) for networkless verification
    clerk_authorized_parties: str = ""  # comma-separated origins allowed to use tokens, e.g. https://app.ondra.ai
    # Roles that must have a second factor (MFA) when signing in with Clerk. Managers too: they see every VIP.
    clerk_mfa_roles: str = "admin,manager"
    # Ondra's own passwords have no second factor, so a public site refuses them unless this says otherwise. Only for
    # a staging site holding demo data, never production (sign-in there is Clerk, with MFA).
    allow_local_auth_on_public_site: bool = False

    # --- AI ---
    anthropic_api_key: str = ""
    # Set explicitly so an ANTHROPIC_BASE_URL in the shell can't redirect the app's traffic.
    anthropic_api_base: str = "https://api.anthropic.com"
    model_conversation: str = "claude-sonnet-5-5"
    model_fast: str = "claude-haiku-5-5"
    agent_effort: str = "low"
    # Voyage AI embeddings for knowledge search. Without a key, a local mock embedder is used.
    voyage_api_key: str = ""
    # Run the agent in the background after the webhook returns (production), or inline (tests, evals).
    agent_inline: bool = False

    # --- Channels. Each uses its mock until its flag is on. ---
    mock_webhook_secret: str = "mock-secret"
    feature_whatsapp: bool = False
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v27.0"
    feature_sms: bool = False
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_messaging_service_sid: str = ""
    # Calling a missed caller back through the dealer's line (services/bridge.py). Off: a mock that places nothing;
    # with MOCK_BRIDGE_AUTOPLAY it plays a call out against the local webhooks so the flow can be seen.
    feature_call_bridge: bool = False
    # VIP calls through the VIP desk (services/vip_desk.py): ring their person, then the dealer's fixed message with
    # press 1 / press 2. Off until the SIP REFER target is verified (TODO(verify) there); the domain is the Twilio
    # Programmable Voice SIP domain whose Voice URL points at /webhooks/voice/vip.
    feature_vip_desk: bool = False
    vip_desk_sip_domain: str = ""
    mock_bridge_autoplay: bool = False
    mock_bridge_answered_by: str = "human"  # what the mock's answering-machine detection reports: human, machine_start
    feature_email: bool = False
    postmark_server_token: str = ""
    postmark_inbound_user: str = ""
    postmark_inbound_password: str = ""

    def public_site_problems(self) -> list[str]:
        """Development defaults that are in the repo, so must never guard a public (https) site: with them, anyone
        could sign tokens as any user or post fake customer messages."""
        if not self.is_public_site:
            return []
        problems = []
        if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("dev-only"):
            problems.append("JWT_SECRET is the development default or shorter than 32 characters")
        if len(self.booking_link_secret) < 32:
            problems.append("BOOKING_LINK_SECRET is empty or shorter than 32 characters")
        if self.mock_webhook_secret in ("", "mock-secret"):
            problems.append("MOCK_WEBHOOK_SECRET is the development default")
        if self.auth_provider == "clerk" and not self.clerk_authorized_parties.strip():
            problems.append("CLERK_AUTHORIZED_PARTIES is empty (set it to the dashboard's origin, e.g. https://app.useondra.com)")
        if self.auth_provider == "local" and not self.allow_local_auth_on_public_site:
            problems.append("AUTH_PROVIDER is local (passwords with no second factor); use clerk, or set "
                            "ALLOW_LOCAL_AUTH_ON_PUBLIC_SITE=true on a staging site with demo data only")
        # A real channel switched on without its secret would accept forged webhooks (an empty HMAC key, or empty
        # basic auth, is one anyone can produce). The adapters refuse too; this stops the site starting at all.
        needs = {
            "FEATURE_WHATSAPP": (self.feature_whatsapp, {"WHATSAPP_APP_SECRET": self.whatsapp_app_secret,
                                                          "WHATSAPP_VERIFY_TOKEN": self.whatsapp_verify_token}),
            "FEATURE_SMS": (self.feature_sms, {"TWILIO_AUTH_TOKEN": self.twilio_auth_token}),
            "FEATURE_CALL_BRIDGE": (self.feature_call_bridge, {"TWILIO_AUTH_TOKEN": self.twilio_auth_token}),
            "FEATURE_VIP_DESK": (self.feature_vip_desk, {"TWILIO_AUTH_TOKEN": self.twilio_auth_token}),
            "FEATURE_EMAIL": (self.feature_email, {"POSTMARK_INBOUND_USER": self.postmark_inbound_user,
                                                    "POSTMARK_INBOUND_PASSWORD": self.postmark_inbound_password}),
        }
        for flag, (on, secrets) in needs.items():
            missing = [name for name, value in secrets.items() if not value]
            if on and missing:
                problems.append(f"{flag} is on but {', '.join(missing)} is empty")
        return problems

    @property
    def is_public_site(self) -> bool:
        """Staging and production: the dashboard is served over https. Mock-only paths are switched off there."""
        return self.app_base_url.startswith("https://")

    @property
    def cookie_secure(self) -> bool:
        return self.app_base_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
