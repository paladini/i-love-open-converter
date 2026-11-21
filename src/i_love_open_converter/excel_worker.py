"""Extract detected PDF tables and selectable text into a bounded XLSX workbook."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

MAX_PAGES = 200
MAX_PAGE_PIXELS = 16_000_000
MAX_TABLE_CELLS = 200_000
MAX_TEXT_LINES = 100_000
MAX_CELL_CHARS = 32_767
MAX_OUTPUT_BYTES = 256 * 1024**2


class NoSpreadsheetDataError(Exception):
    """The PDF contains no detected table cells or selectable text."""


def _limit_resources() -> None:
    if sys.platform != "linux":
        raise RuntimeError("Linux resource limits are required")
    import resource

    if platform.machine().lower() == "aarch64":
        resource.setrlimit(resource.RLIMIT_DATA, (1536 * 1024**2, 1536 * 1024**2))
    else:
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))


def _cell_text(value: str | None) -> str:
    text = "" if value is None else str(value)
    if len(text) > MAX_CELL_CHARS:
        raise ValueError("PDF cell exceeds the Excel text limit")
    return text


def _extract(document):
    import pymupdf

    tables: list[tuple[int, int, int, list[str]]] = []
    lines: list[tuple[int, int, str]] = []
    table_cells = 0
    for page_number, page in enumerate(document, start=1):
        rect = page.rect
        if rect.width <= 0 or rect.height <= 0:
            raise ValueError("Invalid PDF page dimensions")
        width_px, height_px = rect.width * 150 / 72, rect.height * 150 / 72
        if width_px * height_px > MAX_PAGE_PIXELS:
            raise ValueError("PDF page exceeds the pixel limit")

        page_tables = []
        for table_number, table in enumerate(
            page.find_tables(strategy="lines", use_layout=False).tables, start=1
        ):
            rows = [[_cell_text(value) for value in row] for row in table.extract()]
            if not any(value for row in rows for value in row):
                continue
            columns = max(map(len, rows), default=0)
            if columns > 16_384:
                raise ValueError("PDF table exceeds the Excel column limit")
            table_cells += sum(len(row) for row in rows)
            if table_cells > MAX_TABLE_CELLS:
                raise ValueError("PDF tables exceed the cell limit")
            tables.extend(
                (page_number, table_number, row_number, row)
                for row_number, row in enumerate(rows, start=1)
            )
            page_tables.append(pymupdf.Rect(table.bbox))

        for block in page.get_text("dict", sort=True).get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                text = "".join(span.get("text", "") for span in line.get("spans", []))
                text = _cell_text(text.strip())
                if not text:
                    continue
                x0, y0, x1, y1 = line["bbox"]
                center = pymupdf.Point((x0 + x1) / 2, (y0 + y1) / 2)
                if any(table_rect.contains(center) for table_rect in page_tables):
                    continue
                lines.append((page_number, len(lines) + 1, text))
                if len(lines) > MAX_TEXT_LINES:
                    raise ValueError("PDF text exceeds the line limit")

    if not tables and not lines:
        raise NoSpreadsheetDataError
    return tables, lines


def _write_workbook(destination: Path, tables, lines) -> None:
    import xlsxwriter

    workbook = xlsxwriter.Workbook(
        str(destination),
        {
            "constant_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
            "strings_to_numbers": False,
        },
    )
    header = workbook.add_format({"bold": True, "bg_color": "#EAF0FF"})
    try:
        if tables:
            worksheet = workbook.add_worksheet("Tables")
            column_count = max(len(row) for _, _, _, row in tables)
            headings = ["Source page", "Table", "Row"] + [
                f"Column {index}" for index in range(1, column_count + 1)
            ]
            for column, value in enumerate(headings):
                worksheet.write_string(0, column, value, header)
            for output_row, (page, table, row_number, values) in enumerate(tables, start=1):
                metadata = (str(page), str(table), str(row_number))
                for column, value in enumerate(metadata):
                    worksheet.write_string(output_row, column, value)
                for column, value in enumerate(values, start=3):
                    worksheet.write_string(output_row, column, value)
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, len(tables), len(headings) - 1)
            worksheet.set_column(0, 2, 12)
            worksheet.set_column(3, len(headings) - 1, 20)

        if lines:
            worksheet = workbook.add_worksheet("Text")
            for column, value in enumerate(("Source page", "Line", "Text")):
                worksheet.write_string(0, column, value, header)
            for output_row, (page, line_number, value) in enumerate(lines, start=1):
                worksheet.write_string(output_row, 0, str(page))
                worksheet.write_string(output_row, 1, str(line_number))
                worksheet.write_string(output_row, 2, value)
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, len(lines), 2)
            worksheet.set_column(0, 1, 12)
            worksheet.set_column(2, 2, 80)
    finally:
        workbook.close()


def main(source: Path, destination: Path) -> None:
    _limit_resources()
    import pymupdf

    try:
        with pymupdf.open(source) as document:
            if document.is_encrypted or not 1 <= document.page_count <= MAX_PAGES:
                raise ValueError("PDF is encrypted or exceeds the page limit")
            tables, lines = _extract(document)
        destination.parent.mkdir(parents=True, exist_ok=True)
        _write_workbook(destination, tables, lines)
        if destination.stat().st_size > MAX_OUTPUT_BYTES:
            raise ValueError("XLSX exceeds the output limit")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    try:
        main(Path(sys.argv[1]), Path(sys.argv[2]))
    except NoSpreadsheetDataError:
        raise SystemExit(3) from None
