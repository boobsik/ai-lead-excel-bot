"""Middleware для внедрения зависимостей в хендлеры."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.analyzer import LeadAnalyzer
from bot.config import Settings
from bot.db import LeadRepository


class ServicesMiddleware(BaseMiddleware):
    """Прокидывает settings/repo/analyzer в data хендлеров."""

    def __init__(
        self,
        *,
        settings: Settings,
        repository: LeadRepository,
        analyzer: LeadAnalyzer,
    ) -> None:
        self.services = {
            "settings": settings,
            "repository": repository,
            "analyzer": analyzer,
        }

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data.update(self.services)
        return await handler(event, data)
