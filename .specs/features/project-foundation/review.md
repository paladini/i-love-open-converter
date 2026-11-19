# Review — PDF watermarks and page numbers

## Verdict: Changes required

The PDF operations, routes, and upload-first steps are present. The implementation does not meet all of the approved screen criteria, and the tests do not prove several output and validation rules that the plan makes binding.

## Findings

### [P1] Home screen departs from the binding catalog capture

Criterion 1 requires the centered hero and the PDF/image catalog in the captured grouping and order. At the captured 731 × 720 viewport, the app hero is left-aligned beside artwork. The category row also omits “Fluxos de trabalho”. The captures list 31 PDF cards and 13 image cards, while the current catalog shows 8 PDF cards and 4 image cards; the roadmap explains that other operations are staged, but this acceptance criterion still asks for the captured catalog. The PDF group also says “06 disponíveis” although eight cards are shown.

Evidence: `.specs/features/project-foundation/captures/ilovepdf-home.aria.yml`, `.specs/features/project-foundation/captures/iloveimg-home.aria.yml`, `src/i_love_open_converter/templates/index.html:59-95`, and the browser view at 731 × 720.

### [P1] The tool page cannot clear the selected PDF

Criterion 9 says “Remover arquivo” clears selected inputs and restores the empty upload state. The options screen only offers “Trocar arquivo”; its handler hides the options step and returns to upload without clearing `pdfInput` or the selected filename. The user cannot return to the empty state without choosing a replacement file.

Evidence: `src/i_love_open_converter/templates/pdf-tool.html:37` and `src/i_love_open_converter/static/js/pdf-tool.js:85-89`.

### [P2] Output and validation tests leave important rules unproved

Criterion 6 requires checks for dimensions, text preservation, anchor placement, and selected visual settings. The watermark tests only assert that the text exists on each page, and that an image exists on each page. They would still pass if placement, opacity, font, color, or page dimensions were wrong; they do not inspect the image watermark’s preserved alpha. The page-number test exercises only `page_number_total` in English and checks the resulting text; it does not cover `number`, `number_total`, or the Portuguese wording. For the new option validation, the only malformed-option assertion is a page-number color value, while the plan covers ranges and types for position, opacity, font, size, start number, and watermark text.

Evidence: `tests/test_api.py:396-493`. Code inspection shows validation and rendering branches for these options, but the required tests would not fail for several incorrect implementations of those branches.

### [P2] Tool page titles differ from their captured headings

The captures and the plan’s source-departure table retain headings “Inserir marca d'água em um PDF” and “Inserir números de páginas a um PDF”. The current pages show shortened titles “Marca d’água” and “Números de página”. The upload-first state and option controls are present, but these headings do not preserve the bound capture text.

Evidence: `.specs/features/project-foundation/captures/ilovepdf-watermark.aria.yml`, `.specs/features/project-foundation/captures/ilovepdf-page-numbers.aria.yml`, and `src/i_love_open_converter/templates/pdf-tool.html:16`.

## Checks performed

- Read the project request, approved plan, capability inventory, captures, implementation, and tests.
- Opened the home page and both PDF tool routes in a browser. Verified the initial upload-only state, selected-PDF options, watermark text and image modes, page-number options, and the PDF editing category filter.
- Checked the tool-page layout at 360 px with no horizontal overflow; checked the home page at the captured 731 × 720 viewport.
- Did not submit a job in the running app. A generated one-page PDF was used only to reveal the client-side options step; it was removed afterward.
- The implementation suite and Ruff checks were reported passing by the builder before review. No PR push was performed.

## Fix pass

Completed after this review:

- Restored all 31 PDF and 13 image catalog entries in the captured order; future-stage tools are disabled and labeled “Em breve” / “Coming soon”. Added the workflow and image category chips and centered the home hero.
- Updated the tool-page headings/descriptions to match their captures and changed “Trocar arquivo” into a clearing “Remover arquivo” action that restores the empty upload step.
- Expanded tests to check the catalog count, watermark font/color/opacity/placement and page dimensions, image alpha mask, all three page-number formats in PT-BR/English, and invalid option boundaries.
- Verified the upload-first page and catalog in the browser after the corrections. No file-processing job was submitted there.
- Verification after the fix pass: full pytest suite, Ruff check, Node syntax checks for both scripts, and `git diff --check` passed.
