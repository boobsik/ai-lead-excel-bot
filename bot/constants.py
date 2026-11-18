"""Общие константы домена."""

from __future__ import annotations

CATEGORIES: tuple[str, ...] = ("Бот", "Парсер", "Автоматизация", "Другое")

URGENCY_HIGH = "Высокая"
URGENCY_NORMAL = "Обычная"
URGENCIES: tuple[str, ...] = (URGENCY_HIGH, URGENCY_NORMAL)

NO_BUDGET = "Не указан"

MIN_LEAD_LENGTH = 15
MAX_LEAD_LENGTH = 3500
