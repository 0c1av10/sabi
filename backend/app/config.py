from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database: sqlite for local dev, postgresql+asyncpg://... for Supabase/prod
    database_url: str = "sqlite+aiosqlite:///./sabi.db"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    # When true, the agent uses a deterministic scripted engine (no LLM calls).
    agent_mock_mode: bool = False

    # WhatsApp Cloud API
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "sabi-verify-token"
    whatsapp_api_version: str = "v21.0"
    # When true, outbound WhatsApp messages are only logged (no HTTP calls).
    whatsapp_mock_mode: bool = True

    # Panel auth
    session_secret: str = "change-me-in-production"

    backend_base_url: str = "http://localhost:8000"


settings = Settings()
