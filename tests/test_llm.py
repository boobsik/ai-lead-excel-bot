"""Тесты интеграции с OpenAI-совместимым API (через httpx.MockTransport)."""

from __future__ import annotations

import json

import httpx
import pytest

from bot.analyzer import LeadAnalyzer

SAMPLE_TEXT = "Нужен телеграм-бот для приёма заявок с сайта, бюджет 40 000 руб, срочно"


@pytest.mark.asyncio
async def test_llm_response_is_parsed_and_normalized() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        content = (
            "```json\n"
            '{"category": "бот", "estimated_budget": "40 000 ₽", '
            '"urgency": "high", "summary": "Клиенту нужен бот для заявок"}\n'
            "```"
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    analyzer = LeadAnalyzer(
        api_key="sk-test",
        base_url="https://llm.example/v1/",
        model="test-model",
        client=client,
    )
    try:
        result = await analyzer.analyze(SAMPLE_TEXT)
    finally:
        await analyzer.aclose()
        await client.aclose()

    assert result.category == "Бот"
    assert result.estimated_budget == "40 000 ₽"
    assert result.urgency == "Высокая"
    assert result.summary == "Клиенту нужен бот для заявок."
    assert analyzer.endpoint == "https://llm.example/v1/chat/completions"
    assert requests[0]["model"] == "test-model"
    assert requests[0]["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_local_parser() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "provider is down"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    analyzer = LeadAnalyzer(
        api_key="sk-test",
        base_url="https://llm.example/v1",
        model="test-model",
        client=client,
    )
    try:
        result = await analyzer.analyze(SAMPLE_TEXT)
    finally:
        await analyzer.aclose()
        await client.aclose()

    assert result.category == "Бот"
    assert result.estimated_budget == "40 000 ₽"
    assert result.urgency == "Высокая"


@pytest.mark.asyncio
async def test_empty_key_never_calls_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("LLM не должен вызываться без API-ключа")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    analyzer = LeadAnalyzer(api_key="", client=client)
    try:
        result = await analyzer.analyze(SAMPLE_TEXT)
    finally:
        await analyzer.aclose()
        await client.aclose()

    assert result.category == "Бот"
    assert result.summary.endswith(".")
