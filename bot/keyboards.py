"""Inline-клавиатуры бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def start_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Оставить заявку", callback_data="lead:new")
    builder.button(text="📊 Excel-отчёт", callback_data="report:download")
    builder.button(text="✨ Демо-заявки", callback_data="demo:seed")
    builder.adjust(1, 2)
    return builder.as_markup()


def after_lead_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Ещё одна заявка", callback_data="lead:new")
    builder.button(text="📊 Скачать Excel-отчёт", callback_data="report:download")
    builder.adjust(1, 1)
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✖️ Отменить", callback_data="lead:cancel")
    return builder.as_markup()
