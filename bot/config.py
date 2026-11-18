"""Загрузка и валидация конфигурации из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
SUPPORTED_PROXY_SCHEMES = ("http", "socks4", "socks5")


class ConfigError(RuntimeError):
    """Невалидная или неполная конфигурация приложения."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Настройки приложения, собранные из окружения."""

    bot_token: str
    admin_id: int | None = None
    llm_api_key: str = ""
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_timeout: float = 25.0
    proxy_url: str | None = None
    db_path: Path = field(default_factory=lambda: PROJECT_ROOT / "leads.db")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key.strip())


def _parse_admin_id(raw: str) -> int | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(
            "ADMIN_ID должен быть числом — узнать свой ID можно у @userinfobot."
        ) from exc
    if value <= 0:
        raise ConfigError("ADMIN_ID должен быть положительным числом.")
    return value


def _parse_timeout(raw: str) -> float:
    raw = raw.strip()
    if not raw:
        return 25.0
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError("LLM_TIMEOUT должен быть числом (секунды).") from exc
    if value <= 0:
        raise ConfigError("LLM_TIMEOUT должен быть больше нуля.")
    return value


def _resolve_db_path(raw: str) -> Path:
    path = Path(os.path.expandvars(raw.strip() or "leads.db")).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _parse_proxy_url(raw: str) -> str | None:
    """Нормализует и валидирует необязательный PROXY_URL."""

    raw = raw.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"http://{raw}"

    try:
        parsed = urlsplit(raw)
        port = parsed.port
        hostname = parsed.hostname
    except ValueError as exc:
        raise ConfigError(
            "PROXY_URL указан некорректно. Пример: http://127.0.0.1:10808 "
            "или socks5://127.0.0.1:1080."
        ) from exc

    scheme = parsed.scheme.lower()
    if scheme == "socks5h":
        # aiohttp-socks не знает socks5h, но aiogram и так включает rdns=True.
        scheme = "socks5"
        parsed = parsed._replace(scheme=scheme)

    if scheme not in SUPPORTED_PROXY_SCHEMES:
        raise ConfigError(
            f"PROXY_URL: схема «{parsed.scheme}» не поддерживается. "
            "Используйте http://, socks4:// или socks5://."
        )
    if not hostname or not port:
        raise ConfigError(
            "PROXY_URL: укажите хост и порт прокси, например "
            "http://127.0.0.1:10808 или socks5://127.0.0.1:1080."
        )
    if any(char.isspace() for char in raw):
        raise ConfigError("PROXY_URL не должен содержать пробелов.")

    return parsed.geturl()


def load_settings(env_file: str | Path | None = None) -> Settings:
    """Читает `.env` и переменные окружения, возвращает валидные настройки.

    Явно переданные переменные окружения имеют приоритет над `.env`.
    """

    if env_file is not None:
        load_dotenv(dotenv_path=env_file, override=False)
    else:
        load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError(
            "BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен из @BotFather."
        )
    if ":" not in token:
        raise ConfigError(
            "BOT_TOKEN выглядит некорректно: ожидается формат «123456789:AA...» от @BotFather."
        )
    token_id, _, token_secret = token.partition(":")
    if not token_id.isdigit() or not token_secret:
        raise ConfigError(
            "BOT_TOKEN выглядит некорректно: до двоеточия должен быть числовой ID бота, "
            "после — секретная часть токена."
        )
    if "your-token" in token.lower() or "botfather" in token.lower():
        raise ConfigError(
            "BOT_TOKEN всё ещё похож на значение из .env.example. "
            "Укажите реальный токен, полученный у @BotFather."
        )

    base_url = os.getenv("LLM_BASE_URL", "").strip() or DEFAULT_LLM_BASE_URL
    model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_LLM_MODEL

    return Settings(
        bot_token=token,
        admin_id=_parse_admin_id(os.getenv("ADMIN_ID", "")),
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_base_url=base_url.rstrip("/"),
        llm_model=model,
        llm_timeout=_parse_timeout(os.getenv("LLM_TIMEOUT", "")),
        proxy_url=_parse_proxy_url(os.getenv("PROXY_URL", "")),
        db_path=_resolve_db_path(os.getenv("DB_PATH", "leads.db")),
    )
