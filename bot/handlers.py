"""Хендлеры Telegram-бота: заявки, отчёты и демо-данные."""

from __future__ import annotations

import asyncio
import html
import logging
from datetime import timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)

from bot.analyzer import LeadAnalyzer, analyze_locally
from bot.config import Settings
from bot.constants import MAX_LEAD_LENGTH, MIN_LEAD_LENGTH, URGENCY_HIGH
from bot.db import LeadRepository
from bot.excel_report import default_report_filename, report_to_bytes
from bot.keyboards import after_lead_keyboard, cancel_keyboard, start_keyboard
from bot.models import Lead, utc_now
from bot.texts import (
    ANALYZING,
    ASK_LEAD,
    CANCELLED,
    DEMO_DONE,
    ERROR_TEXT,
    HELP,
    REPORT_CAPTION,
    REPORT_EMPTY,
    SHORT_HINT,
    TOO_LONG,
    WELCOME,
    format_admin_lead,
    format_user_lead,
)

logger = logging.getLogger(__name__)
router = Router(name="leads")


class LeadForm(StatesGroup):
    waiting_for_text = State()


# Реалистичные демо-заявки: (username, full_name, telegram_id, hours_ago, text)
DEMO_LEADS: tuple[tuple[str, str, int, int, str], ...] = (
    (
        "ivan_petrov",
        "Иван Петров",
        100100001,
        2,
        "Нужен парсер цен конкурентов с Wildberries и Ozon: собирать цены раз в день, "
        "складывать в Excel и присылать в Telegram. Бюджет 15000 руб, срок 3 дня.",
    ),
    (
        "olga_smm",
        "Ольга Смирнова",
        100100002,
        9,
        "Телеграм-бот для приёма заявок с сайта: меню, сбор контактов и уведомления "
        "менеджеру в amoCRM. Бюджет до 40 000 ₽, срок 2 недели.",
    ),
    (
        "dmitry_ops",
        "Дмитрий Козлов",
        100100003,
        26,
        "Автоматизация ежедневных отчётов: выгрузка из CRM в Google Sheets через API, "
        "сводка по продажам каждое утро. Бюджет 25 000 руб, срочно.",
    ),
    (
        "anna_market",
        "Анна Волкова",
        100100004,
        52,
        "Нужен парсер отзывов с маркетплейса: 10 000 товаров, выгрузка в CSV, "
        "фильтр по рейтингу. Бюджет 30 тыс. руб., срок месяц.",
    ),
    (
        "sergey_startup",
        "Сергей Морозов",
        100100005,
        75,
        "Хочу телеграм-бота-квиз для сбора лидов и интеграцию с amoCRM, чтобы заявки "
        "сразу попадали в воронку. Бюджет 50000 рублей, срок 5 дней.",
    ),
)


def _callback_keyboard() -> InlineKeyboardMarkup:
    return after_lead_keyboard()


async def _reply(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Отвечает в чат, где нажата кнопка (с fallback на личку)."""

    if isinstance(callback.message, Message):
        try:
            await callback.message.answer(text, reply_markup=reply_markup)
            return
        except Exception:  # сообщение могло быть удалено
            logger.debug("Не удалось ответить на callback в чате", exc_info=True)
    await callback.bot.send_message(callback.from_user.id, text, reply_markup=reply_markup)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    name = message.from_user.first_name if message.from_user else "друг"
    await message.answer(
        WELCOME.format(name=html.escape(name, quote=False)),
        reply_markup=start_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(HELP, reply_markup=start_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(CANCELLED, reply_markup=start_keyboard())


@router.callback_query(F.data == "lead:new")
async def cb_new_lead(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LeadForm.waiting_for_text)
    await callback.answer("Жду описание задачи ✍️")
    await _reply(callback, ASK_LEAD, reply_markup=cancel_keyboard())


@router.callback_query(F.data == "lead:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    await _reply(callback, CANCELLED, reply_markup=start_keyboard())


@router.message(F.text, ~F.text.startswith("/"))
async def handle_lead_text(
    message: Message,
    state: FSMContext,
    settings: Settings,
    repository: LeadRepository,
    analyzer: LeadAnalyzer,
) -> None:
    """Принимает заявку в свободной форме — в любом состоянии диалога."""

    text = (message.text or "").strip()
    if len(text) < MIN_LEAD_LENGTH:
        await message.answer(SHORT_HINT)
        return
    if len(text) > MAX_LEAD_LENGTH:
        await message.answer(TOO_LONG.format(limit=MAX_LEAD_LENGTH))
        return

    await state.clear()
    status = await message.answer(ANALYZING)

    try:
        analysis = await analyzer.analyze(text)
        user = message.from_user
        lead = Lead(
            source_text=text,
            category=analysis.category,
            estimated_budget=analysis.estimated_budget,
            urgency=analysis.urgency,
            summary=analysis.summary,
            telegram_id=user.id if user else None,
            username=user.username if user else None,
            full_name=user.full_name if user else None,
        )
        await repository.add_lead(lead)
    except Exception:
        logger.exception("Не удалось обработать заявку пользователя %s", message.chat.id)
        await status.edit_text(ERROR_TEXT)
        return

    try:
        await status.edit_text(format_user_lead(lead), reply_markup=_callback_keyboard())
    except Exception:
        logger.warning("Не удалось обновить сообщение со статусом", exc_info=True)
        await message.answer(format_user_lead(lead), reply_markup=_callback_keyboard())

    await _notify_admin(message.bot, settings, lead)


async def _notify_admin(bot: Bot, settings: Settings, lead: Lead) -> None:
    if settings.admin_id is None:
        logger.debug("ADMIN_ID не задан — уведомление пропущено")
        return
    try:
        await bot.send_message(settings.admin_id, format_admin_lead(lead))
    except Exception:
        logger.warning("Не удалось отправить уведомление админу", exc_info=True)


async def _send_report(message: Message, repository: LeadRepository) -> None:
    leads = await repository.list_leads()
    if not leads:
        await message.answer(REPORT_EMPTY, reply_markup=start_keyboard())
        return

    await message.answer("📊 Собираю Excel-отчёт…")
    data = await asyncio.to_thread(report_to_bytes, leads)
    high_count = sum(lead.urgency == URGENCY_HIGH for lead in leads)
    now = utc_now()
    caption = REPORT_CAPTION.format(
        total=len(leads),
        high=high_count,
        timestamp=now.strftime("%d.%m.%Y %H:%M"),
    )
    document = BufferedInputFile(
        file=data,
        filename=default_report_filename(now),
    )
    await message.answer_document(
        document=document,
        caption=caption,
        reply_markup=start_keyboard(),
    )


@router.message(Command("report"))
async def cmd_report(message: Message, state: FSMContext, repository: LeadRepository) -> None:
    """Отчёт открыт всем — это демо-проект для портфолио."""

    await state.clear()
    await _send_report(message, repository)


@router.callback_query(F.data == "report:download")
async def cb_report(callback: CallbackQuery, repository: LeadRepository) -> None:
    await callback.answer("Готовлю отчёт…")
    if not isinstance(callback.message, Message):
        await callback.bot.send_message(callback.from_user.id, REPORT_EMPTY)
        return
    await _send_report(callback.message, repository)


async def _seed_demo(repository: LeadRepository) -> tuple[int, int]:
    now = utc_now()
    leads: list[Lead] = []
    for username, full_name, telegram_id, hours_ago, text in DEMO_LEADS:
        analysis = analyze_locally(text)
        leads.append(
            Lead(
                source_text=text,
                category=analysis.category,
                estimated_budget=analysis.estimated_budget,
                urgency=analysis.urgency,
                summary=analysis.summary,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                created_at=now - timedelta(hours=hours_ago),
            )
        )
    ids = await repository.add_many(leads)
    total = await repository.count()
    return len(ids), total


@router.message(Command("demo"))
async def cmd_demo(message: Message, state: FSMContext, repository: LeadRepository) -> None:
    await state.clear()
    added, total = await _seed_demo(repository)
    await message.answer(
        DEMO_DONE.format(added=added, total=total),
        reply_markup=start_keyboard(),
    )


@router.callback_query(F.data == "demo:seed")
async def cb_demo(callback: CallbackQuery, repository: LeadRepository) -> None:
    added, total = await _seed_demo(repository)
    await callback.answer(f"Добавлено {added} заявок")
    await _reply(
        callback,
        DEMO_DONE.format(added=added, total=total),
        reply_markup=start_keyboard(),
    )


@router.message()
async def fallback_handler(message: Message) -> None:
    """Подсказка на нетекстовые сообщения (фото, стикеры и т.п.)."""

    await message.answer(
        "Я принимаю заявки текстом 🙂 Напиши задачу сообщением или нажми /start.",
        reply_markup=start_keyboard(),
    )
