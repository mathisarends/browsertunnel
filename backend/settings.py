from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrowserSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BROWSER_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    executable: str | None = None
    cdp_url: str | None = None
    headless: bool = True
    width: int = Field(default=1600, gt=0)
    height: int = Field(default=900, gt=0)
    screencast_quality: int = Field(default=80, ge=0, le=100)
    startup_timeout: float = Field(default=15, gt=0)
