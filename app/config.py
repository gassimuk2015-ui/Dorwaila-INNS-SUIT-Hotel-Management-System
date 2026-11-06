from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    secret_key: str = Field(min_length=32)
    database_url: str = "sqlite:///./dorwaila_dev.db"
    access_token_minutes: int = 30
    reporting_currency: str = "SLE"
    hotel_timezone: str = "Africa/Freetown"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

