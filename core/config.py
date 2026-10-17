from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Automotive Workshop Command Center"
    API_VERSION: str = "v1"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite:///./workshop_demo.db"

    # ── HITL Guardrail Thresholds ─────────────────────────────────────────────
    QUOTE_APPROVAL_THRESHOLD_THB: float = 3000.0
    CUSTOMER_INACTIVE_MONTHS: int = 6
    OIL_CHANGE_KM: int = 10000
    OIL_CHANGE_MONTHS: int = 6
    BATTERY_CHANGE_YEARS: int = 2
    TIRE_CHANGE_KM: int = 40000

    # ── Security ──────────────────────────────────────────────────────────────
    MOCK_API_KEY: str = "workshop-secret-2026"
    REQUIRE_PASSWORD: bool = False  # True = ask for the shop password (MOCK_API_KEY) before using the program

    # ── LINE OA ───────────────────────────────────────────────────────────────
    LINE_OA_CHANNEL_TOKEN: str = "MOCK_LINE_TOKEN"
    LINE_OA_CHANNEL_SECRET: str = ""  # set in .env — never commit the real secret
    LINE_OA_MOCK_URL: str = "https://api.line.me/v2/bot/message/push"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
