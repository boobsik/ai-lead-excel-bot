"""Тексты и HTML-карточки для сообщений бота."""

from __future__ import annotations

import html
from datetime import UTC, datetime

from bot.constants import URGENCY_HIGH
from bot.models import Lead

WELCOME = """👋 <b>Привет, {name}!</b>

Я AI-ассистент студии разработки. Принимаю заявки, сам определяю категорию, бюджет и срочность, а затем собираю всё в аккуратный Excel-отчёт.

<b>Как это работает:</b>
1. Опиши задачу одним сообщением.
2. AI разберёт заявку за пару секунд.
3. Ты сразу увидишь карточку, а админ — уведомление.
4. Команда /report пришлёт готовый .xlsx.

<b>Пример:</b>
<i>«Нужен парсер цен конкурентов с маркетплейса в Excel, бюджет 15000 руб, срок 3 дня»</i>

Просто напиши задачу в чат или нажми кнопку ниже 👇"""

ASK_LEAD = """✍️ <b>Опиши заявку</b>

Расскажи в свободной форме: что нужно сделать, какой бюджет и сроки. Чем больше деталей, тем точнее AI-анализ.

Например:
<i>«Нужен Telegram-бот для приёма заказов с интеграцией в amoCRM, бюджет 40 000 руб, срок 2 недели»</i>

Отправь одним сообщением. Отменить — /cancel."""

SHORT_HINT = """🤏 Слишком коротко для заявки.

Опиши задачу чуть подробнее (минимум 15 символов): что сделать, бюджет, сроки. Например:
<i>«Нужен парсер цен конкурентов с Wildberries в Excel, срок 3 дня»</i>"""

TOO_LONG = """✂️ Заявка получилась слишком длинной (максимум {limit} символов).

Сократи описание до сути — остальное можно уточнить у менеджера."""

ANALYZING = "⏳ Анализирую заявку…"

CANCELLED = "Ок, отменил. Чтобы начать заново — /start"

HELP = """ℹ️ <b>Что я умею</b>

<b>Заявка</b> — просто отправь текст задачи в чат.
<b>/report</b> — Excel-отчёт по всем заявкам.
<b>/demo</b> — добавить 5 демо-заявок и сразу проверить отчёт.
<b>/cancel</b> — отменить ввод заявки.
<b>/start</b> — вернуться в начало.

AI-анализ определяет категорию, бюджет, срочность и краткое резюме. Без API-ключа работает локальный умный парсер.

Данные хранятся локально в SQLite, наружу не уходят."""

ERROR_TEXT = """😔 Не получилось обработать заявку.

Попробуй отправить ещё раз через минуту или напиши /start."""

REPORT_EMPTY = """📭 <b>В базе пока нет заявок.</b>

Добавь 5 реалистичных демо-заявок командой /demo — и сразу сможешь скачать готовый Excel-отчёт через /report."""

DEMO_DONE = """✅ <b>Добавлено {added} демо-заявок.</b>

Всего в базе: <b>{total}</b>. Теперь можно скачать отчёт — он уже выглядит как настоящий 😉"""

REPORT_CAPTION = """📊 <b>Excel-отчёт готов</b>

Заявок: <b>{total}</b>
Высокая срочность: <b>{high}</b>
Сформирован: {timestamp} UTC

Внутри два листа: «Заявки» с фильтрами и подсветкой и «Сводка» с аналитикой."""

USER_LEAD_SAVED = """✅ <b>Заявка №{lead_id} принята!</b>

🏷 <b>Категория:</b> {category}
💰 <b>Бюджет:</b> {budget}
⚡ <b>Срочность:</b> {urgency}
📝 <b>Суть:</b> {summary}

Мы сохранили заявку и передали её менеджеру. Если нужно что-то уточнить — просто напиши ещё одно сообщение."""

ADMIN_LEAD = """🔥 <b>Новая заявка #{lead_id}</b>

👤 <b>Клиент:</b> {client}
🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>
🕒 <b>Дата:</b> {created_at} UTC
🏷 <b>Категория:</b> {category}
💰 <b>Бюджет:</b> {budget}
⚡ <b>Срочность:</b> {urgency}

📝 <b>Текст заявки:</b>
<blockquote>{source_text}</blockquote>

🤖 <b>AI-резюме:</b> {summary}"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def _format_dt(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(UTC)
    return value.strftime("%d.%m.%Y %H:%M")


def _truncate(value: str, limit: int) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"


def _urgency_icon(urgency: str) -> str:
    return "⚡" if urgency == URGENCY_HIGH else "🕒"


def format_user_lead(lead: Lead) -> str:
    return USER_LEAD_SAVED.format(
        lead_id=lead.id or "—",
        category=esc(lead.category),
        budget=esc(lead.estimated_budget),
        urgency=esc(lead.urgency),
        summary=esc(_truncate(lead.summary, 300)),
    )


def format_admin_lead(lead: Lead, *, limit: int = 900) -> str:
    if lead.username:
        client = (
            f'<a href="tg://user?id={lead.telegram_id}">@{esc(lead.username)}</a>'
            if lead.telegram_id
            else f"@{esc(lead.username)}"
        )
        if lead.full_name:
            client = f"{esc(lead.full_name)} ({client})"
    else:
        client = esc(lead.full_name or "без username")

    return ADMIN_LEAD.format(
        lead_id=lead.id or "—",
        client=client,
        telegram_id=lead.telegram_id or "—",
        created_at=_format_dt(lead.created_at),
        category=esc(lead.category),
        budget=esc(lead.estimated_budget),
        urgency=f"{_urgency_icon(lead.urgency)} {esc(lead.urgency)}",
        source_text=esc(_truncate(lead.source_text, limit)),
        summary=esc(_truncate(lead.summary, 300)),
    )
