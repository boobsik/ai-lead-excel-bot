"""Тесты вспомогательной логики хендлеров и карточек."""

from __future__ import annotations

import pytest

from bot.analyzer import LeadAnalyzer
from bot.config import Settings
from bot.db import LeadRepository
from bot.handlers import _seed_demo
from bot.texts import format_admin_lead, format_user_lead


@pytest.mark.asyncio
async def test_demo_seeds_five_realistic_leads(tmp_path) -> None:
    async with LeadRepository(tmp_path / "leads.db") as repository:
        added, total = await _seed_demo(repository)
        leads = await repository.list_leads()

    assert added == 5
    assert total == 5
    assert len(leads) == 5
    assert len({lead.source_text for lead in leads}) == 5
    assert sum(lead.urgency == "Высокая" for lead in leads) == 2
    assert {lead.category for lead in leads} == {"Парсер", "Бот", "Автоматизация"}
    assert all(lead.id is not None for lead in leads)
    assert all(lead.username and lead.full_name for lead in leads)


def test_admin_card_escapes_user_html(lead_factory) -> None:
    lead = lead_factory(
        source_text="<script>alert('xss')</script> нужен парсер",
        summary="<b>Опасный</b> текст",
        username="tester",
    )

    card = format_admin_lead(lead)

    assert "<script>" not in card
    assert "&lt;script&gt;" in card
    assert "&lt;b&gt;Опасный&lt;/b&gt;" in card
    assert "Новая заявка" in card
    assert "@tester" in card


def test_user_card_contains_analysis(lead_factory) -> None:
    lead = lead_factory(id=42)
    card = format_user_lead(lead)

    assert "Заявка №42" in card
    assert "Парсер" in card
    assert "15 000 ₽" in card
    assert "Высокая" in card


def test_analyzer_from_settings_uses_llm_config() -> None:
    settings = Settings(
        bot_token="123:test",
        llm_api_key="sk-test",
        llm_base_url="https://example.test/v1/",
        llm_model="custom-model",
        llm_timeout=12.0,
    )

    analyzer = LeadAnalyzer.from_settings(settings)

    assert analyzer.api_key == "sk-test"
    assert analyzer.endpoint == "https://example.test/v1/chat/completions"
    assert analyzer.model == "custom-model"
    assert analyzer.timeout == 12.0
