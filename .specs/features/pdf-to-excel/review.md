# Review

**Verdict: changes required before merge.** The PDF-to-Excel page and workbook flow work in the exercised case, but the isolation guard runs after opening the untrusted PDF in the worker process. The required isolation failure test does not catch this. The workbook-ordering and source-reference criteria also lack assertions that would detect regressions.

## Evidence

- Read `.specs/features/pdf-to-excel/request.md` sentence by sentence and compared it with the approved plan, API route, worker dispatch, extractor, UI and README documentation.
- No design captures exist for this feature. Started the feature page at `http://127.0.0.1:8772/tools/pdf-to-excel` with a throwaway database in `.specs/features/pdf-to-excel/review-data/`; the worker used `--network none`, `OFFICE_NETWORK_ISOLATED=1` and user `1000:1000`. The English page accepted one generated sample PDF, displayed the success status and exposed a `Download XLSX` link. The reviewed UI state is English; the template provides both PT-BR and English labels and the language selector was verified.
- Ran `rtk proxy uv run pytest -q tests/test_pdf_to_excel.py`: 10 passed.
- The tests cover the detected-table/text happy path, literal `00123` and `=SUM(1,1)` values, absence of formula XML and external links, invalid/encrypted/multiple inputs, scanned-only input with no download, page/pixel/table-cell/text-line bounds, timeout, and worker unavailability.

## Findings

### [P1] Check isolation before opening the PDF

`src/i_love_open_converter/pdf_ops.py:843` calls `_open_pdf(source)` before the `pdf.to_excel` branch checks `word_isolated()` at line 909. Thus a worker started on an unsupported or network-connected host parses attacker-controlled PDF data before returning `excel_unavailable`; the new child is gated, but the parent-side parser is not. This contradicts the plan's fail-closed worker boundary for untrusted PDFs.

Reproduction: with `word_isolated` forced to return `False` and `_open_pdf` replaced by a function that raises `RuntimeError("PDF OPENED BEFORE ISOLATION CHECK")`, calling `process_pdf("pdf.to_excel", ...)` raised that sentinel from line 843, before reaching the isolation error. The current `test_pdf_to_excel_requires_isolated_worker` at `tests/test_pdf_to_excel.py:138` checks only that the job fails with `excel_unavailable` and has no download; it passes while this unsafe parse still occurs. Move the guard ahead of `_open_pdf` for this operation, and add a test asserting the PDF opener is never called when isolation is unavailable.

### [P2] Assert workbook ordering and source references

The plan's acceptance criteria 2 and 3 require source page/table/row references and ordering. The extractor appears to build records in page/table/row order and uses sorted text blocks, but `test_pdf_to_excel_extracts_tables_and_text_as_literal_strings` at `tests/test_pdf_to_excel.py:55` checks only that selected strings and a `Source page` heading occur somewhere in the XML. It would still pass if records were reordered or page/table/row metadata were wrong or omitted from data rows. Add a multi-page/multi-table fixture and assert parsed workbook rows, source identifiers and text line order, so the requirements are protected by regression tests.

## Fix-pass scope

The isolation issue is a correctness/security defect under the approved worker boundary. The missing ordering assertions are a test gap against explicit plan criteria. No code or running application data was changed during this review; the disposable review app and its temporary data were stopped and removed.

## Fix pass

- Moved network-isolation checks for PDF-to-Word, PDF-to-PowerPoint and PDF-to-Excel ahead of `_open_pdf`, so none of these Office-conversion paths parses the input in an unsupported worker. The Excel regression test replaces `_open_pdf` with a sentinel and proves the job fails with `excel_unavailable` without invoking it.
- Added a two-page, three-table workbook fixture. The regression test parses both worksheet XML files and checks exact page/table/row identifiers, table sequence, and text line order across pages.
- Focused verification: `uv run pytest -q tests/test_pdf_to_excel.py tests/test_pdf_to_word.py tests/test_pdf_to_powerpoint.py` passed (27 tests).
