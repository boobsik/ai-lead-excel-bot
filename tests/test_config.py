"""Тесты загрузки конфигурации."""

from __future__ import annotations

import pytest

from bot.config import PROJECT_ROOT, ConfigError, load_settings

_ENV_KEYS = (
    "BOT_TOKEN",
    "ADMIN_ID",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_TIMEOUT",
    "PROXY_URL",
    "DB_PATH",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_loads_settings_from_env_file(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BOT_TOKEN=123456789:AA-test-token\n"
        "ADMIN_ID=777\n"
        "LLM_API_KEY=sk-test\n"
        "LLM_BASE_URL=https://openrouter.ai/api/v1/\n"
        "LLM_MODEL=openai/gpt-4o-mini\n"
        "PROXY_URL=socks5h://127.0.0.1:1080\n"
        "DB_PATH=data/leads.db\n",
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.bot_token == "123456789:AA-test-token"
    assert settings.admin_id == 777
    assert settings.llm_enabled is True
    assert settings.llm_base_url == "https://openrouter.ai/api/v1"
    assert settings.llm_model == "openai/gpt-4o-mini"
    assert settings.proxy_url == "socks5://127.0.0.1:1080"
    assert settings.db_path == PROJECT_ROOT / "data" / "leads.db"


def test_empty_key_disables_llm(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("BOT_TOKEN=1:abc\nLLM_API_KEY=\n", encoding="utf-8")

    settings = load_settings(env_file)

    assert settings.llm_enabled is False
    assert settings.admin_id is None
    assert settings.proxy_url is None
    assert settings.llm_base_url.startswith("https://api.openai.com")


def test_missing_token_raises_friendly_error(tmp_path) -> None:
    with pytest.raises(ConfigError, match="BOT_TOKEN"):
        load_settings(tmp_path / "missing.env")


def test_invalid_admin_id_raises(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("BOT_TOKEN=1:abc\nADMIN_ID=not-a-number\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="ADMIN_ID"):
        load_settings(env_file)


def test_placeholder_token_raises_helpful_error(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("BOT_TOKEN=123456789:AAH-your-token-from-botfather\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="env.example"):
        load_settings(env_file)


def test_proxy_url_without_scheme_defaults_to_http(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("BOT_TOKEN=1:abc\nPROXY_URL=127.0.0.1:10808\n", encoding="utf-8")

    settings = load_settings(env_file)

    assert settings.proxy_url == "http://127.0.0.1:10808"


@pytest.mark.parametrize(
    "proxy_url",
    [
        "ftp://127.0.0.1:1080",
        "https://127.0.0.1:8080",
        "http://127.0.0.1",
        "socks5://:1080",
        "http://127.0.0.1:not-a-port",
    ],
)
def test_invalid_proxy_url_raises(tmp_path, proxy_url: str) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"BOT_TOKEN=1:abc\nPROXY_URL={proxy_url}\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="PROXY_URL"):
        load_settings(env_file)
