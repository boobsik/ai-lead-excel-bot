"""Тесты SQLite-репозитория."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bot.db import LeadRepository


@pytest.mark.asyncio
async def test_saves_leads_and_lists_newest_first(tmp_path, lead_factory) -> None:
    db_path = tmp_path / "leads.db"

    async with LeadRepository(db_path) as repository:
        older = lead_factory(
            source_text="Старая заявка",
            created_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
        newer = lead_factory(
            source_text="Новая заявка",
            username=None,
            full_name="Без Юзернейма",
            created_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        )

        assert await repository.add_lead(older) == 1
        assert await repository.add_lead(newer) == 2
        assert await repository.count() == 2

        leads = await repository.list_leads()
        assert [lead.source_text for lead in leads] == ["Новая заявка", "Старая заявка"]
        assert leads[0].username is None
        assert leads[0].full_name == "Без Юзернейма"
        assert leads[0].created_at == datetime(2026, 2, 1, 10, 0, tzinfo=UTC)
        assert leads[0].category == "Парсер"
        assert leads[0].urgency == "Высокая"

        limited = await repository.list_leads(limit=1)
        assert len(limited) == 1
        assert limited[0].source_text == "Новая заявка"


@pytest.mark.asyncio
async def test_data_persists_between_connections(tmp_path, lead_factory) -> None:
    db_path = tmp_path / "persistent" / "leads.db"
    lead = lead_factory(source_text="Проверка персистентности")

    async with LeadRepository(db_path) as repository:
        await repository.add_many([lead])
        assert await repository.count() == 1

    assert db_path.exists()

    async with LeadRepository(db_path) as reopened:
        leads = await reopened.list_leads()
        assert await reopened.count() == 1
        assert len(leads) == 1
        assert leads[0].source_text == "Проверка персистентности"
        assert leads[0].summary == lead.summary


@pytest.mark.asyncio
async def test_add_many_empty_returns_empty(tmp_path) -> None:
    async with LeadRepository(tmp_path / "leads.db") as repository:
        assert await repository.add_many([]) == []
        assert await repository.count() == 0
