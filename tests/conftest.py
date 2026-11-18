"""Общие фикстуры тестов."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from bot.models import Lead


@pytest.fixture
def lead_factory() -> Callable[..., Lead]:
    """Фабрика заявок с разумными значениями по умолчанию."""

    def make(**overrides: Any) -> Lead:
        defaults: dict[str, Any] = {
            "source_text": (
                "Нужен парсер цен конкурентов с маркетплейса в Excel, бюджет 15000 руб, срок 3 дня"
            ),
            "category": "Парсер",
            "estimated_budget": "15 000 ₽",
            "urgency": "Высокая",
            "summary": "Нужен парсер цен конкурентов с маркетплейса в Excel.",
            "telegram_id": 42,
            "username": "tester",
            "full_name": "Тест Тестов",
            "created_at": datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        }
        defaults.update(overrides)
        return Lead(**defaults)

    return make
