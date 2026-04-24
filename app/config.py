from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bot_token: SecretStr
    openai_key: SecretStr
    openai_model: str = "gpt-4o"
    tavily_key: SecretStr | None = None
    allowed_usernames: list[str] = []
    proxy: str | None = None


settings = Settings()
