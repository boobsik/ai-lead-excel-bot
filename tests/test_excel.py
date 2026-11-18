"""Тесты генерации Excel-отчёта."""

from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook

from bot.excel_report import (
    HIGH_URGENCY_FILL,
    report_to_bytes,
    save_report,
)


def test_report_has_styled_headers_and_highlights(tmp_path, lead_factory) -> None:
    normal = lead_factory(
        source_text="Обычная заявка на бота",
        category="Бот",
        urgency="Обычная",
        summary="Нужен телеграм-бот.",
    )
    urgent = lead_factory(
        source_text="Срочная заявка на парсер",
        category="Парсер",
        urgency="Высокая",
    )

    path = save_report([normal, urgent], tmp_path / "reports" / "leads.xlsx")
    assert path.exists()
    assert path.stat().st_size > 5_000

    workbook = load_workbook(path)
    assert workbook.sheetnames == ["Заявки", "Сводка"]

    sheet = workbook["Заявки"]
    assert sheet["A1"].value == "Отчёт по клиентским заявкам"
    assert sheet["A1"].font.bold is True
    assert sheet["A4"].value == "ID"
    assert sheet["A4"].font.bold is True
    assert sheet.freeze_panes == "A5"
    assert sheet.auto_filter.ref == "A4:I6"

    # Строка 5 — обычная заявка, строка 6 — срочная (подсвечена).
    assert sheet.cell(row=5, column=1).fill.fgColor.rgb.endswith("F5F7FB")
    assert sheet.cell(row=6, column=1).fill.fgColor.rgb.endswith(HIGH_URGENCY_FILL)
    assert sheet.cell(row=6, column=8).font.bold is True
    assert sheet.cell(row=6, column=8).value == "Высокая"


def test_report_autosizes_columns_and_wraps_text(tmp_path, lead_factory) -> None:
    lead = lead_factory()
    path = save_report([lead], tmp_path / "leads.xlsx")
    sheet = load_workbook(path)["Заявки"]

    text_width = sheet.column_dimensions["E"].width
    assert 30 <= text_width <= 60
    assert sheet.cell(row=5, column=5).alignment.wrap_text is True
    assert sheet.cell(row=5, column=5).value.startswith("Нужен парсер")
    assert sheet.row_dimensions[5].height is not None


def test_summary_sheet_counts_categories_and_urgency(tmp_path, lead_factory) -> None:
    leads = [
        lead_factory(category="Парсер", urgency="Высокая"),
        lead_factory(category="Парсер", urgency="Обычная"),
        lead_factory(category="Бот", urgency="Обычная"),
    ]
    path = save_report(leads, tmp_path / "leads.xlsx")
    summary = load_workbook(path)["Сводка"]

    assert summary["A5"].value == "Категория"
    counts = {
        summary.cell(row=row, column=1).value: summary.cell(row=row, column=2).value
        for row in range(6, 10)
    }
    assert counts == {"Бот": 1, "Парсер": 2, "Автоматизация": 0, "Другое": 0}
    assert summary["A14"].value == "Высокая"
    assert summary["B14"].value == 1
    assert summary["A15"].value == "Обычная"
    assert summary["B15"].value == 2


def test_empty_report_is_valid_and_informative(tmp_path) -> None:
    path = save_report([], tmp_path / "empty.xlsx")
    workbook = load_workbook(path)
    sheet = workbook["Заявки"]

    assert "Заявок пока нет" in sheet["A5"].value
    assert workbook["Сводка"]["B10"].value == 0


def test_report_neutralizes_formula_injection(tmp_path, lead_factory) -> None:
    lead = lead_factory(source_text='=HYPERLINK("http://evil.example","click")')
    path = save_report([lead], tmp_path / "leads.xlsx")

    cell = load_workbook(path)["Заявки"]["E5"]

    assert cell.data_type == "s"
    assert cell.value.startswith("=HYPERLINK")


def test_report_to_bytes_is_a_real_xlsx() -> None:
    data = report_to_bytes([])
    assert data.startswith(b"PK")
    assert load_workbook(BytesIO(data)).sheetnames == ["Заявки", "Сводка"]
