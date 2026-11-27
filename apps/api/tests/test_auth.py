

def test_a_public_site_refuses_development_secrets(monkeypatch):
    from ondra_api.config import Settings

    local = Settings(app_base_url="http://localhost:3001")
    assert local.public_site_problems() == []
    public = Settings(app_base_url="https://app.useondra.com", jwt_secret="dev-only-change-me-dev-only-change-me",
                      mock_webhook_secret="mock-secret")
    assert len(public.public_site_problems()) == 2
    safe = Settings(app_base_url="https://app.useondra.com", jwt_secret="x" * 48, mock_webhook_secret="y" * 32)
    assert safe.public_site_problems() == []


def test_demo_users_on_a_public_site_need_their_own_password(monkeypatch):
    import pytest
    from ondra_api import seed
    from ondra_api.config import get_settings

    monkeypatch.setenv("APP_BASE_URL", "https://app.useondra.com")
    get_settings.cache_clear()
    try:
        monkeypatch.delenv("SEED_PASSWORD", raising=False)
        with pytest.raises(SystemExit):
            seed.seed_password()
        monkeypatch.setenv("SEED_PASSWORD", seed.DEV_PASSWORD)
        with pytest.raises(SystemExit):
            seed.seed_password()
        monkeypatch.setenv("SEED_PASSWORD", "a-long-staging-password")
        assert seed.seed_password() == "a-long-staging-password"
    finally:
        monkeypatch.delenv("APP_BASE_URL")
        get_settings.cache_clear()
