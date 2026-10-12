from datetime import time

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Restaurant Operations & Supply Chain API"
    database_url: str = "sqlite:///./restaurant.db"
    # All business dates/times (shifts, audits, orders, delivery days) are in this zone,
    # regardless of the server's own clock setting.
    timezone: str = "Europe/Berlin"
    # Orders must be placed before this local time on the day before a delivery day.
    order_cutoff: time = time(14, 0)
    # Apply pending Alembic migrations when the app starts.
    migrate_on_startup: bool = True
    # Receive pending orders automatically every day at this local time (deliveries arrive early).
    auto_receive_enabled: bool = True
    auto_receive_time: time = time(6, 0)
    # Browser origins allowed to call the API (the Vite dev server by default).
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
