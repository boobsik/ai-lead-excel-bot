"""Точка входа приложения: сборка зависимостей и polling."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from bot.analyzer import LeadAnalyzer
from bot.config import ConfigError, Settings, load_settings
from bot.db import LeadRepository
from bot.handlers import router
from bot.middlewares import ServicesMiddleware

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


BOT_COMMANDS = (
    BotCommand(command="start", description="Начать и оставить заявку"),
    BotCommand(command="report", description="Скачать Excel-отчёт"),
    BotCommand(command="demo", description="Добавить 5 демо-заявок"),
    BotCommand(command="help", description="Как пользоваться ботом"),
    BotCommand(command="cancel", description="Отменить ввод заявки"),
)


class IPv4AiohttpSession(AiohttpSession):
    """AiohttpSession только с IPv4 — обход зависаний IPv6 на Windows.

    aiogram хранит параметры коннектора в приватном `_connector_init`.
    Мы аккуратно добавляем туда `family=socket.AF_INET`, не меняя остальные
    настройки (SSL, пул соединений, прокси). Если внутренний API aiogram
    изменится, сессия продолжит работать в обычном режиме.
    """

    def _apply_ipv4_only(self) -> None:
        try:
            self._connector_init["family"] = socket.AF_INET
        except (AttributeError, TypeError):
            logger.warning(
                "Не удалось принудительно включить IPv4 для Telegram. "
                "Используется стандартный коннектор."
            )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._apply_ipv4_only()

    def _setup_proxy_connector(self, proxy: Any) -> None:
        super()._setup_proxy_connector(proxy)
        self._apply_ipv4_only()


def build_bot_session(proxy_url: str | None = None) -> AiohttpSession:
    """Создаёт Telegram-сессию с IPv4-only и опциональным прокси."""

    try:
        if proxy_url:
            return IPv4AiohttpSession(proxy=proxy_url)
        return IPv4AiohttpSession()
    except RuntimeError as exc:
        raise ConfigError(
            "PROXY_URL задан, но пакет aiohttp-socks не установлен. "
            "Выполните: pip install aiohttp-socks"
        ) from exc


def _error_user_id(event: ErrorEvent) -> int | None:
    update = event.update
    message = update.message or update.edited_message
    if message and message.from_user:
        return message.from_user.id
    if update.callback_query:
        return update.callback_query.from_user.id
    return None


async def main(settings: Settings | None = None) -> None:
    """Запускает бота. Настройки можно передать явно (удобно для тестов)."""

    settings = settings or load_settings()
    repository = LeadRepository(settings.db_path)
    await repository.connect()
    analyzer = LeadAnalyzer.from_settings(settings)

    bot = Bot(
        token=settings.bot_token,
        session=build_bot_session(settings.proxy_url),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())

    services = ServicesMiddleware(settings=settings, repository=repository, analyzer=analyzer)
    dispatcher.message.middleware(services)
    dispatcher.callback_query.middleware(services)
    dispatcher.include_router(router)

    async def on_error(event: ErrorEvent) -> bool:
        logger.error(
            "Необработанная ошибка при обработке апдейта",
            exc_info=(type(event.exception), event.exception, event.exception.__traceback__),
        )
        user_id = _error_user_id(event)
        if user_id is not None:
            try:
                await bot.send_message(
                    user_id,
                    "😔 Что-то пошло не так. Попробуй ещё раз или напиши /start.",
                )
            except Exception:
                logger.debug("Не удалось уведомить пользователя об ошибке", exc_info=True)
        return True

    dispatcher.errors.register(on_error)

    try:
        await bot.set_my_commands(BOT_COMMANDS)
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info(
            "Бот запущен | БД: %s | LLM: %s | Прокси: %s",
            settings.db_path,
            f"включён ({settings.llm_model})" if settings.llm_enabled else "локальный fallback",
            "включён" if settings.proxy_url else "не используется",
        )
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await analyzer.aclose()
        await repository.close()
        await bot.session.close()


def cli() -> None:
    setup_logging()
    try:
        asyncio.run(main())
    except ConfigError as exc:
        logger.error("Ошибка конфигурации: %s", exc)
        raise SystemExit(1) from exc
    except TelegramUnauthorizedError as exc:
        logger.error(
            "Telegram отклонил BOT_TOKEN. Проверьте токен в .env — "
            "его можно перевыпустить в @BotFather."
        )
        raise SystemExit(1) from exc
    except TelegramNetworkError as exc:
        logger.error(
            "Не удалось подключиться к Telegram API: %s. "
            "Проверьте интернет/VPN или задайте PROXY_URL в .env "
            "(например, http://127.0.0.1:10808 или socks5://127.0.0.1:1080).",
            exc,
        )
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        logger.info("Бот остановлен.")
