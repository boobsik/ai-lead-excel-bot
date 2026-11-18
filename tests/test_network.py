"""Тесты сетевой сессии Telegram: IPv4-only и прокси."""

from __future__ import annotations

import socket

import pytest

from bot.main import build_bot_session


@pytest.mark.asyncio
async def test_direct_session_uses_ipv4_only() -> None:
    session = build_bot_session()
    try:
        assert session.proxy is None
        assert session._connector_init["family"] == socket.AF_INET
        client_session = await session.create_session()
        assert client_session.connector is not None
        assert client_session.connector.__class__.__name__ == "TCPConnector"
    finally:
        await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "proxy_url",
    [
        "http://127.0.0.1:10808",
        "socks5://127.0.0.1:1080",
    ],
)
async def test_proxy_session_uses_ipv4_and_proxy(proxy_url: str) -> None:
    session = build_bot_session(proxy_url)
    try:
        assert session.proxy == proxy_url
        assert session._connector_init["family"] == socket.AF_INET
        assert session._connector_init["host"] == "127.0.0.1"
        client_session = await session.create_session()
        assert client_session.connector is not None
        assert client_session.connector.__class__.__name__ == "ProxyConnector"
    finally:
        await session.close()
