from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database: sqlite for local dev, postgresql+asyncpg://... for Supabase/prod
    database_url: str = "sqlite+aiosqlite:///./sabi.db"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    # When true, the agent uses a deterministic scripted engine (no LLM calls).
    agent_mock_mode: bool = False

    # WhatsApp Cloud API
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "sabi-verify-token"
    whatsapp_api_version: str = "v21.0"
    # When true, outbound WhatsApp messages are only logged (no HTTP calls).
    whatsapp_mock_mode: bool = True

    whatsapp_provider: str = ""  # zernio | kapso | meta; empty = first configured
    shared_whatsapp_number: str = ""
    frontend_base_url: str = "https://sabi-ecru.vercel.app"

    zernio_api_key: str = ""
    zernio_account_id: str = ""
    zernio_webhook_secret: str = ""

    kapso_api_key: str = ""
    kapso_phone_number_id: str = ""
    kapso_webhook_secret: str = ""
    kapso_api_version: str = "v24.0"

    # Panel auth
    rate_limit_per_phone_hour: int = 20
    simulate_limit_hour: int = 300
    max_message_chars: int = 1000

    session_secret: str = "change-me-in-production"

    # --- Events (FC Producciones demo) ---
    # Seeds three fictional events when the catalog is empty (clearly marked as demo).
    events_demo_seed: bool = True
    events_max_quantity: int = 10
    # Zone prices not verified for this many hours are shown as "por verificar".
    events_stale_hours: int = 72
    events_chat_limit_hour: int = 40
    events_global_limit_hour: int = 600
    events_max_tool_calls: int = 6
    events_agent_timeout_seconds: float = 25.0
    events_max_message_chars: int = 500
    # Optional allowlist (comma separated hosts) for official purchase URLs.
    events_allowed_purchase_hosts: str = ""
    # Admin: allowed emails (comma separated) + shared password. Empty = admin disabled.
    events_admin_emails: str = ""
    events_admin_password: str = ""

    backend_base_url: str = "http://localhost:8000"
    demo_autoseed: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


settings = Settings()
