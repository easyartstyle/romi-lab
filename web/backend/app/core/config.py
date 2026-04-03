import os
from pathlib import Path

from pydantic import BaseModel


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = BACKEND_ROOT / "analytics_web.db"


class Settings(BaseModel):
    app_name: str = "Analytics Web Service"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    database_url: str = os.getenv("ANALYTICS_WEB_DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}")
    secret_key: str = os.getenv("ANALYTICS_WEB_SECRET_KEY", "analytics-web-dev-secret-change-me")
    access_token_expire_days: int = int(os.getenv("ANALYTICS_WEB_ACCESS_TOKEN_EXPIRE_DAYS", "30"))
    invite_token_expire_days: int = int(os.getenv("ANALYTICS_WEB_INVITE_TOKEN_EXPIRE_DAYS", "14"))
    frontend_base_url: str = os.getenv("ANALYTICS_WEB_FRONTEND_BASE_URL", "http://localhost:3000")
    primary_owner_email: str = os.getenv("ANALYTICS_WEB_PRIMARY_OWNER_EMAIL", "easyartstyle@gmail.com")
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]


settings = Settings()