from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from the environment (and a repo-root .env in development). See .env.example."""

    model_config = SettingsConfigDict(env_file=("../../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+asyncpg://ondra_app:ondra_app_dev@localhost:5432/ondra"
    migrations_database_url: str = "postgresql+asyncpg://ondra_owner:ondra_owner_dev@localhost:5432/ondra"
    jwt_secret: str = "dev-only-change-me-dev-only-change-me"
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
    # Owners and admins must have a second factor (MFA) when signing in with Clerk.
    clerk_mfa_roles: str = "admin"

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
        if not self.app_base_url.startswith("https://"):
            return []
        problems = []
        if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("dev-only"):
            problems.append("JWT_SECRET is the development default or shorter than 32 characters")
        if self.mock_webhook_secret in ("", "mock-secret"):
            problems.append("MOCK_WEBHOOK_SECRET is the development default")
        return problems

    @property
    def cookie_secure(self) -> bool:
        return self.app_base_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
