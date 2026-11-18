"""Доменные модели приложения."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Текущее время UTC без микросекунд (удобно для SQLite и Excel)."""

    return datetime.now(UTC).replace(microsecond=0)


@dataclass(slots=True)
class Lead:
    """Клиентская заявка вместе с результатами AI-анализа."""

    source_text: str
    category: str
    estimated_budget: str
    urgency: str
    summary: str
    telegram_id: int | None = None
    username: str | None = None
    full_name: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    id: int | None = None

    @property
    def client_label(self) -> str:
        """Человекочитаемое имя клиента для карточек и Excel."""

        if self.full_name and self.username:
            return f"{self.full_name} (@{self.username})"
        if self.username:
            return f"@{self.username}"
        if self.full_name:
            return self.full_name
        return "—"
