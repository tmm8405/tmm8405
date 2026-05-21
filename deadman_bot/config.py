from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_use_ssl: bool
    smtp_use_tls: bool
    database_path: str
    check_interval_seconds: int
    max_send_attempts: int
    retry_delay_seconds: int


def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value or ""


def _get_bool_env(name: str, default: str) -> bool:
    value = _get_env(name, default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(name: str, default: str, minimum: int = 1) -> int:
    value = _get_env(name, default)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer value") from exc
    if parsed < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}")
    return parsed


def load_settings() -> Settings:
    smtp_user = _get_env("SMTP_USER", required=True)
    return Settings(
        telegram_token=_get_env("TELEGRAM_BOT_TOKEN", required=True),
        smtp_host=_get_env("SMTP_HOST", required=True),
        smtp_port=_get_int_env("SMTP_PORT", "587", minimum=1),
        smtp_user=smtp_user,
        smtp_password=_get_env("SMTP_PASSWORD", required=True),
        smtp_from=_get_env("SMTP_FROM", smtp_user),
        smtp_use_ssl=_get_bool_env("SMTP_USE_SSL", "false"),
        smtp_use_tls=_get_bool_env("SMTP_USE_TLS", "true"),
        database_path=_get_env("DATABASE_PATH", "data/deadman.sqlite"),
        check_interval_seconds=_get_int_env("CHECK_INTERVAL_SECONDS", "60", minimum=5),
        max_send_attempts=_get_int_env("MAX_SEND_ATTEMPTS", "5", minimum=1),
        retry_delay_seconds=_get_int_env("RETRY_DELAY_SECONDS", "300", minimum=30),
    )
