# Independent review: PDF Form Authoring

## Findings

### [P1] Manual text and checkbox fields are rejected on save

- `src/i_love_open_converter/static/js/pdf-forms.js:12`: every field created by dragging gets `choices: ['Option 1', 'Option 2']`, regardless of selected type.
- `src/i_love_open_converter/pdf_ops.py:570-585`: the API rejects non-empty choices for text and checkbox fields.
- Impact: the primary manual authoring flow cannot save the default text or checkbox fields. Only combo, list, and radio fields pass this particular validation.
- Suggested fix: attach `choices` only for radio/combo/list fields, and initialize each choice field's option editor accordingly.

### [P2] Portuguese mode leaves some field controls in English

- `src/i_love_open_converter/templates/pdf-forms.html:1`: the new field type options (`Text`, `Checkbox`, `Radio group`, `Dropdown`, `List`) have no `data-pt` translations.
- Impact: switching to Brazilian Portuguese does not translate all controls, contrary to S1 acceptance criterion 5.
- Suggested fix: add `data-pt`/`data-en` values to each option and ensure the language switch updates option labels.

### [P2] OCR suggestion requests have no concurrency or time budget

- `src/i_love_open_converter/main.py:89-100,607-621`: each request can OCR up to 20 pages in a threadpool, with no endpoint-specific concurrency limit or wall-clock deadline.
- Impact: concurrent uploads can start many local Tesseract jobs and tie up CPU and threadpool capacity. The worker queue's isolation/concurrency controls do not apply to this endpoint.
- Suggested fix: bound concurrent detection requests and add a time limit/cancellation strategy; keep the 20-page and bounded-render limits.

## Review limits

- No tests or live UI checks were run, per the review task instructions.
- PyMuPDF 2.1's documented widget APIs were inspected; creation, save, and reopening behavior still needs CI/integration confirmation.
- Detection is heuristic: it proposes text fields from OCR tokens ending in a colon, plus vector-drawn blank lines and square outlines. It does not infer grouped choices, and raster-only blank lines/checkboxes will not be detected by the vector geometry pass.

## Resolution

- P1 resolved: manual text and checkbox descriptors now use an empty choices list; choice fields alone include options.
- P2 resolved: new field type labels now have Portuguese and English values, and generated field controls are rebuilt on language changes.
- P2 resolved: suggestion requests allow one concurrent OCR subprocess and time out after 90 seconds.
