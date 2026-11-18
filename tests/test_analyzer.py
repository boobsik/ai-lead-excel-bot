"""Тесты локального fallback-анализатора."""

from __future__ import annotations

import pytest

from bot.analyzer import (
    analyze_locally,
    detect_category,
    detect_urgency,
    extract_budget,
    summarize_text,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Нужен парсер цен конкурентов с маркетплейса в Excel, бюджет 15000 руб, срок 3 дня",
            "Парсер",
        ),
        ("Сделайте телеграм-бота для приёма заказов и уведомлений", "Бот"),
        ("Автоматизация отчётов в Google Sheets через API", "Автоматизация"),
        ("Нужен лендинг под ключ с дизайном", "Другое"),
        # «работа» не должна превращаться в «бот» из-за подстроки
        ("Нужна работа с текстами и контент-план", "Другое"),
    ],
)
def test_category_detection(text: str, expected: str) -> None:
    assert detect_category(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("бюджет 15000 руб", "15 000 ₽"),
        ("до 20к", "20 000 ₽"),
        ("$300", "$300"),
        ("1.5 млн рублей", "1 500 000 ₽"),
        ("30 тыс. руб.", "30 000 ₽"),
        ("15000р", "15 000 ₽"),
        ("до 40 000 ₽", "40 000 ₽"),
        ("без бюджета", "Не указан"),
    ],
)
def test_budget_extraction(text: str, expected: str) -> None:
    assert extract_budget(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Нужно срочно, дедлайн завтра", "Высокая"),
        ("Срок 3 дня, бюджет 10 000 руб", "Высокая"),
        ("Срок 2 недели, бюджет 10 000 руб", "Обычная"),
        ("Можно не спеша, в течение месяца", "Обычная"),
    ],
)
def test_urgency_detection(text: str, expected: str) -> None:
    assert detect_urgency(text) == expected


def test_full_analysis_of_portfolio_example() -> None:
    result = analyze_locally(
        "Нужен парсер цен конкурентов с маркетплейса в Excel, бюджет 15000 руб, срок 3 дня"
    )
    assert result.category == "Парсер"
    assert result.estimated_budget == "15 000 ₽"
    assert result.urgency == "Высокая"
    assert result.summary.endswith(".")
    assert "парсер" in result.summary.lower()
    assert len(result.summary) <= 200


def test_summary_is_short_and_single_sentence() -> None:
    long_text = "Нужен телеграм-бот. " + "Очень подробное описание. " * 40
    summary = summarize_text(long_text)
    assert summary.count(".") == 1
    assert len(summary) <= 170
