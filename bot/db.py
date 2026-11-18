"""Асинхронное хранилище заявок в SQLite."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from bot.models import Lead

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TEXT NOT NULL,
    telegram_id      INTEGER,
    username         TEXT,
    full_name        TEXT,
    source_text      TEXT NOT NULL,
    category         TEXT NOT NULL,
    estimated_budget TEXT NOT NULL,
    urgency          TEXT NOT NULL,
    summary          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads (created_at DESC);
"""

_COLUMNS = (
    "id, created_at, telegram_id, username, full_name, "
    "source_text, category, estimated_budget, urgency, summary"
)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _lead_from_row(row: aiosqlite.Row) -> Lead:
    created_at = datetime.fromisoformat(row["created_at"])
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return Lead(
        id=row["id"],
        created_at=created_at,
        telegram_id=row["telegram_id"],
        username=row["username"],
        full_name=row["full_name"],
        source_text=row["source_text"],
        category=row["category"],
        estimated_budget=row["estimated_budget"],
        urgency=row["urgency"],
        summary=row["summary"],
    )


class LeadRepository:
    """Репозиторий заявок. Одна connection на процесс, запись — под lock."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else ":memory:"
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._conn is not None:
            return
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("LeadRepository не подключён: вызовите await connect()")
        return self._conn

    async def add_lead(self, lead: Lead) -> int:
        ids = await self.add_many([lead])
        return ids[0]

    async def add_many(self, leads: Iterable[Lead]) -> list[int]:
        """Сохраняет пачку заявок в одной транзакции. Возвращает их id."""

        items = list(leads)
        if not items:
            return []

        async with self._write_lock:
            ids: list[int] = []
            try:
                for lead in items:
                    cursor = await self.connection.execute(
                        """
                        INSERT INTO leads (
                            created_at, telegram_id, username, full_name,
                            source_text, category, estimated_budget, urgency, summary
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _ensure_utc(lead.created_at).isoformat(timespec="seconds"),
                            lead.telegram_id,
                            lead.username,
                            lead.full_name,
                            lead.source_text,
                            lead.category,
                            lead.estimated_budget,
                            lead.urgency,
                            lead.summary,
                        ),
                    )
                    lead_id = cursor.lastrowid
                    if lead_id is not None:
                        lead.id = lead_id
                        ids.append(lead_id)
                    await cursor.close()
                await self.connection.commit()
            except Exception:
                await self.connection.rollback()
                raise
        return ids

    async def list_leads(self, limit: int | None = None) -> Sequence[Lead]:
        sql = f"SELECT {_COLUMNS} FROM leads ORDER BY created_at DESC, id DESC"
        params: tuple[object, ...] = ()
        if limit is not None:
            if limit <= 0:
                return []
            sql += " LIMIT ?"
            params = (limit,)

        cursor = await self.connection.execute(sql, params)
        try:
            rows = await cursor.fetchall()
        finally:
            await cursor.close()
        return [_lead_from_row(row) for row in rows]

    async def count(self) -> int:
        cursor = await self.connection.execute("SELECT COUNT(*) AS total FROM leads")
        try:
            row = await cursor.fetchone()
        finally:
            await cursor.close()
        return int(row["total"]) if row is not None else 0

    async def __aenter__(self) -> LeadRepository:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
