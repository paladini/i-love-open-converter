# PDF to Excel research

- The full project pins `pymupdf==2.1`; official documentation exposes `Page.find_tables()` with `Table.extract()` cell matrices. A local grid probe showed that the default layout gate suppresses a simple drawn table, while `strategy="lines", use_layout=False` detects its rows; the worker therefore sets these explicitly. Extraction is geometry-dependent; unbordered or unusual tables can be missed, so the tool must not promise exact layout reconstruction. `page.get_text("dict")` supplies selectable text and positions for non-table lines.
- XlsxWriter creates XLSX workbooks and supports constant-memory output. Its default `write()` handler interprets strings beginning with `=` as formulas and URL-like text as hyperlinks. Set `strings_to_formulas=False`, `strings_to_urls=False`, and `strings_to_numbers=False` so PDF content stays literal and preserves leading zeroes.
- Direct extraction probe is in `probe.py`; validate the pinned runtime's table API and expected cell matrix before enabling the tool.
- Preserve the full roadmap; PDF to Excel is one stage, while HTML/URL conversion, OCR and remaining image tools are still required.
