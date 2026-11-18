"""Генерация стилизованного Excel-отчёта по заявкам."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.worksheet import Worksheet

from bot.constants import CATEGORIES, URGENCY_HIGH, URGENCY_NORMAL
from bot.models import Lead

TITLE_FILL = "1F3864"
SUBTITLE_FILL = "E9EEF8"
HEADER_FILL = "2F5597"
HIGH_URGENCY_FILL = "FCE4E4"
BAND_FILL = "F5F7FB"
BORDER_COLOR = "D9DEE8"
TEXT_DARK = "1F2937"
TEXT_MUTED = "5B6472"
HIGH_URGENCY_TEXT = "9C0006"

# (заголовок, ключ, минимальная ширина, максимальная ширина)
COLUMNS: tuple[tuple[str, str, int, int], ...] = (
    ("ID", "id", 6, 8),
    ("Дата (UTC)", "created_at", 17, 18),
    ("Клиент", "client", 16, 30),
    ("Telegram ID", "telegram_id", 13, 16),
    ("Текст заявки", "source_text", 30, 60),
    ("Категория", "category", 13, 20),
    ("Бюджет", "estimated_budget", 13, 20),
    ("Срочность", "urgency", 11, 14),
    ("AI-резюме", "summary", 30, 50),
)

_THIN = Side(style="thin", color=BORDER_COLOR)
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _fill(color: str) -> PatternFill:
    return PatternFill(fill_type="solid", start_color=color, end_color=color)


def _format_dt(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(UTC)
    return value.strftime("%d.%m.%Y %H:%M")


def _column_value(lead: Lead, key: str) -> object:
    if key == "client":
        return lead.client_label
    if key == "created_at":
        return _format_dt(lead.created_at)
    if key == "id":
        return lead.id if lead.id is not None else "—"
    if key == "telegram_id":
        return lead.telegram_id if lead.telegram_id is not None else "—"
    return getattr(lead, key)


def _estimate_lines(value: object, width: int) -> int:
    if value is None:
        return 1
    lines = 0
    for part in str(value).split("\n"):
        lines += max(1, math.ceil(len(part) / max(width - 2, 1)))
    return lines


def _style_title(ws: Worksheet, title: str, subtitle: str) -> None:
    last_column = len(COLUMNS)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_column)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_column)

    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    title_cell.fill = _fill(TITLE_FILL)
    title_cell.alignment = Alignment(vertical="center", horizontal="left", indent=1)

    subtitle_cell = ws.cell(row=2, column=1, value=subtitle)
    subtitle_cell.font = Font(name="Calibri", size=10, color=TEXT_MUTED)
    subtitle_cell.fill = _fill(SUBTITLE_FILL)
    subtitle_cell.alignment = Alignment(vertical="center", horizontal="left", indent=1)

    ws.row_dimensions[1].height = 32
    ws.row_dimensions[2].height = 22
    ws.row_dimensions[3].height = 6


def _write_header(ws: Worksheet, row: int) -> None:
    for column, (title, _key, _min_width, _max_width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=row, column=column, value=title)
        cell.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        cell.fill = _fill(HEADER_FILL)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER
    ws.row_dimensions[row].height = 30


def _write_data_row(ws: Worksheet, lead: Lead, row: int, index: int) -> None:
    is_high = lead.urgency == URGENCY_HIGH
    row_color = HIGH_URGENCY_FILL if is_high else (BAND_FILL if index % 2 == 0 else "FFFFFF")

    for column, (_title, key, _min_width, _max_width) in enumerate(COLUMNS, start=1):
        value = _column_value(lead, key)
        cell = ws.cell(row=row, column=column, value=value)
        if isinstance(value, str):
            # Защита от formula injection: текст из заявки не должен стать формулой.
            cell.data_type = "s"
            cell.number_format = "@"
        cell.fill = _fill(row_color)
        cell.border = _BORDER
        cell.font = Font(
            name="Calibri",
            size=10,
            color=TEXT_DARK,
            bold=key == "urgency" and is_high,
        )

        if key in {"id", "created_at", "telegram_id", "category", "estimated_budget", "urgency"}:
            cell.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        else:
            cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

        if key == "urgency":
            if is_high:
                cell.font = Font(name="Calibri", size=10, bold=True, color=HIGH_URGENCY_TEXT)
            else:
                cell.font = Font(name="Calibri", size=10, color=TEXT_MUTED)
        elif key == "estimated_budget":
            cell.font = Font(name="Calibri", size=10, bold=True, color=TEXT_DARK)

    lines = max(
        _estimate_lines(lead.source_text, 55),
        _estimate_lines(lead.summary, 45),
        _estimate_lines(lead.client_label, 25),
    )
    ws.row_dimensions[row].height = min(max(20, lines * 14 + 6), 150)


def _autosize_columns(ws: Worksheet, leads: Sequence[Lead]) -> None:
    for column, (title, key, min_width, max_width) in enumerate(COLUMNS, start=1):
        longest = len(title)
        for lead in leads:
            value = _column_value(lead, key)
            for line in str(value).split("\n"):
                longest = max(longest, len(line))
        width = min(max(longest + 2, min_width), max_width)
        ws.column_dimensions[get_column_letter(column)].width = width


def _build_leads_sheet(ws: Worksheet, leads: Sequence[Lead], generated_at: datetime) -> None:
    ws.title = "Заявки"
    ws.sheet_properties.tabColor = TITLE_FILL
    ws.sheet_view.zoomScale = 90
    ws.freeze_panes = "A5"

    subtitle = (
        f"Сформирован: {generated_at:%d.%m.%Y %H:%M} UTC  •  "
        f"Всего заявок: {len(leads)}  •  Высокая срочность: "
        f"{sum(lead.urgency == URGENCY_HIGH for lead in leads)}"
    )
    _style_title(ws, "Отчёт по клиентским заявкам", subtitle)
    _write_header(ws, 4)

    if not leads:
        last_column = len(COLUMNS)
        ws.merge_cells(start_row=5, start_column=1, end_row=5, end_column=last_column)
        cell = ws.cell(
            row=5, column=1, value="Заявок пока нет — добавьте демо-данные командой /demo"
        )
        cell.font = Font(name="Calibri", size=11, italic=True, color=TEXT_MUTED)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[5].height = 36
        for column in range(1, last_column + 1):
            ws.cell(row=5, column=column).border = _BORDER
        _autosize_columns(ws, leads)
        return

    for index, lead in enumerate(leads):
        _write_data_row(ws, lead, row=5 + index, index=index)

    last_row = 4 + len(leads)
    ws.auto_filter.ref = f"A4:{get_column_letter(len(COLUMNS))}{last_row}"
    ws.print_title_rows = "1:4"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    _autosize_columns(ws, leads)


def _summary_header(ws: Worksheet, row: int, headers: Sequence[str]) -> None:
    for column, title in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=column, value=title)
        cell.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        cell.fill = _fill(HEADER_FILL)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER
    ws.row_dimensions[row].height = 24


def _summary_section(ws: Worksheet, row: int, title: str, last_column: int = 3) -> None:
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_column)
    cell = ws.cell(row=row, column=1, value=title)
    cell.font = Font(name="Calibri", size=11, bold=True, color=TITLE_FILL)
    cell.alignment = Alignment(vertical="center", horizontal="left")
    ws.row_dimensions[row].height = 24


def _build_summary_sheet(ws: Worksheet, leads: Sequence[Lead], generated_at: datetime) -> None:
    ws.title = "Сводка"
    ws.sheet_properties.tabColor = "70AD47"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 14

    ws.merge_cells("A1:C1")
    title = ws["A1"]
    title.value = "Сводка по заявкам"
    title.font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    title.fill = _fill(TITLE_FILL)
    title.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 32

    ws.merge_cells("A2:C2")
    subtitle = ws["A2"]
    subtitle.value = (
        f"Сформирован: {generated_at:%d.%m.%Y %H:%M} UTC  •  Всего заявок: {len(leads)}"
    )
    subtitle.font = Font(name="Calibri", size=10, color=TEXT_MUTED)
    subtitle.fill = _fill(SUBTITLE_FILL)
    subtitle.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[2].height = 22

    category_counts = Counter(lead.category for lead in leads)
    urgency_counts = Counter(lead.urgency for lead in leads)

    _summary_section(ws, 4, "По категориям")
    _summary_header(ws, 5, ("Категория", "Заявок", "Доля"))

    total = len(leads)
    for offset, category in enumerate(CATEGORIES):
        row = 6 + offset
        count = category_counts.get(category, 0)
        values = (category, count, (count / total) if total else 0)
        for column, value in enumerate(values, start=1):
            cell = ws.cell(row=row, column=column, value=value)
            cell.border = _BORDER
            cell.font = Font(name="Calibri", size=10, color=TEXT_DARK, bold=column == 1)
            cell.alignment = Alignment(
                horizontal="left" if column == 1 else "center", vertical="center"
            )
            if column == 3:
                cell.number_format = "0%"

    total_row = 6 + len(CATEGORIES)
    for column, value in enumerate(("Итого", total, 1 if total else 0), start=1):
        cell = ws.cell(row=total_row, column=column, value=value)
        cell.border = _BORDER
        cell.fill = _fill(SUBTITLE_FILL)
        cell.font = Font(name="Calibri", size=10, bold=True, color=TITLE_FILL)
        cell.alignment = Alignment(
            horizontal="left" if column == 1 else "center", vertical="center"
        )
        if column == 3:
            cell.number_format = "0%"

    urgency_row = total_row + 2
    _summary_section(ws, urgency_row, "По срочности")
    _summary_header(ws, urgency_row + 1, ("Срочность", "Заявок"))
    for offset, urgency in enumerate((URGENCY_HIGH, URGENCY_NORMAL)):
        row = urgency_row + 2 + offset
        count = urgency_counts.get(urgency, 0)
        for column, value in enumerate((urgency, count), start=1):
            cell = ws.cell(row=row, column=column, value=value)
            cell.border = _BORDER
            cell.font = Font(
                name="Calibri",
                size=10,
                bold=urgency == URGENCY_HIGH,
                color=HIGH_URGENCY_TEXT if urgency == URGENCY_HIGH else TEXT_DARK,
            )
            if urgency == URGENCY_HIGH:
                cell.fill = _fill(HIGH_URGENCY_FILL)
            cell.alignment = Alignment(
                horizontal="left" if column == 1 else "center", vertical="center"
            )

    note_row = urgency_row + 6
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=3)
    note = ws.cell(
        row=note_row,
        column=1,
        value="Отчёт сгенерирован автоматически: ai-lead-excel-bot",
    )
    note.font = Font(name="Calibri", size=9, italic=True, color=TEXT_MUTED)
    note.alignment = Alignment(horizontal="left", vertical="center")


def build_report(leads: Sequence[Lead], *, generated_at: datetime | None = None) -> Workbook:
    """Собирает книгу Excel с листами «Заявки» и «Сводка»."""

    leads = list(leads)
    generated_at = generated_at or datetime.now(UTC)

    workbook = Workbook()
    leads_sheet = workbook.active
    assert leads_sheet is not None
    _build_leads_sheet(leads_sheet, leads, generated_at)
    summary_sheet = workbook.create_sheet("Сводка")
    _build_summary_sheet(summary_sheet, leads, generated_at)

    workbook.properties.title = "Отчёт по клиентским заявкам"
    workbook.properties.subject = "AI-анализ заявок"
    workbook.properties.creator = "AI Lead Excel Bot"
    workbook.properties.description = (
        "Автоматический отчёт по заявкам, обработанным Telegram-ботом."
    )
    return workbook


def report_to_bytes(leads: Sequence[Lead]) -> bytes:
    """Возвращает .xlsx как байты — удобно для отправки в Telegram."""

    stream = BytesIO()
    build_report(leads).save(stream)
    return stream.getvalue()


def save_report(leads: Sequence[Lead], path: str | Path) -> Path:
    """Сохраняет отчёт на диск и возвращает путь."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    build_report(leads).save(destination)
    return destination


def default_report_filename(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"leads_report_{now:%Y-%m-%d_%H-%M}.xlsx"
