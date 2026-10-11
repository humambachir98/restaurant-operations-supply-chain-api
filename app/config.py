from datetime import time

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Restaurant Shift & Inventory API"
    database_url: str = "sqlite:///./restaurant.db"
    # All business dates/times (shifts, audits, orders, delivery days) are in this zone,
    # regardless of the server's own clock setting.
    timezone: str = "Europe/Berlin"
    # Orders must be placed before this local time on the day before a delivery day.
    order_cutoff: time = time(14, 0)
    # Apply pending Alembic migrations when the app starts.
    migrate_on_startup: bool = True

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
