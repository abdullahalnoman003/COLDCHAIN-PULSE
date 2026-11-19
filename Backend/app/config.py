import os
from dataclasses import dataclass


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        # Vercel's filesystem is read-only except /tmp (data is NOT persistent there).
        return "sqlite:////tmp/coldchain.db" if os.getenv("VERCEL") else "sqlite:///./coldchain.db"
    # Neon / Supabase / Heroku style URLs
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str = _db_url()
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    token_minutes: int = int(os.getenv("TOKEN_MINUTES", "480"))
    bcrypt_rounds: int = int(os.getenv("BCRYPT_ROUNDS", "12"))
    warning_margin_c: float = float(os.getenv("WARNING_MARGIN_C", "1.0"))
    critical_breach_minutes: int = int(os.getenv("CRITICAL_BREACH_MINUTES", "10"))
    login_max_failures: int = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
    login_lock_minutes: int = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    auto_create_tables: bool = os.getenv("AUTO_CREATE_TABLES", "1") == "1"


settings = Settings()
