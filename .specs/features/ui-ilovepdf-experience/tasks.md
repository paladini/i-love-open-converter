# iLovePDF & iLoveIMG Experience Redesign — Tasks

**Design**: `.specs/features/ui-ilovepdf-experience/design.md`
**Status**: Done

---

## Execution Plan

```
T1 (CSS Design System) ──→ T2 (Home Catalog & Studio HTML) ──→ T3 (Interactive Studio JS & File Cards) ──→ T4 (Unify 18 Dedicated Tool Pages) ──→ T6 (Bespoke SVG Icons & Instant Search) ──→ T7 (Paper-Sheet Previews & Per-Card Remove) ──→ T8 (Universal Dedicated Dropzone Shell & Full Validation)
```

---

## Task Breakdown

### T1: Overhaul CSS Design System (`app.css`)
- **What**: Replace `app.css` with the OKLCH domain-adaptive design system (iLovePDF Crimson Coral & iLoveIMG Cobalt Indigo), responsive 2-column Studio Workspace grid, visual file card grid, sticky navigation header, and 360px mobile breakpoints.
- **Where**: `src/i_love_open_converter/static/css/app.css`
- **Depends on**: None
- **Requirement**: UI-01, UI-02, UI-06
- **Tests**: e2e (`tests/test_mobile_ui.py`)
- **Gate**: quick

### T2: Redesign Home Catalog & Studio Workspace Template (`index.html`)
- **What**: Upgrade `index.html` with the unified iLovePDF/iLoveIMG top header, semantic SVG icons for all 50 tool cards, prominent 2-column Studio Workspace (`#converter-panel` with `.workspace-stage` and `.workspace-sidebar`), and workflow ribbon while preserving all 50 `.tool-card` count and form control IDs.
- **Where**: `src/i_love_open_converter/templates/index.html`
- **Depends on**: T1
- **Requirement**: UI-02, UI-04
- **Tests**: integration (`tests/test_api.py`, `tests/test_conversion_coverage.py`)
- **Gate**: quick

### T3: Enhance Client Studio Logic & Visual File Cards (`app.js`)
- **What**: Upgrade `app.js` to switch domain themes (`data-domain="pdf|image"`), sync `?tool=` URL parameter, smoothly focus the workspace when a tool card is clicked, render visual file cards with live image thumbnails (`URL.createObjectURL`) and format badges in `#selected-file-name`, and support adding more files in batch mode.
- **Where**: `src/i_love_open_converter/static/js/app.js`
- **Depends on**: T2
- **Requirement**: UI-02, UI-03
- **Tests**: e2e (`tests/test_mobile_ui.py`, `tests/test_api.py`)
- **Gate**: full

### T4: Unify Header, Upload Dropzones, and Footer Across 18 Dedicated Tool Templates
- **What**: Update all 18 `/tools/*` HTML templates with the unified `.site-header` (brand mark, quick navigation links, `100% local` pill, language picker), enhanced `.pdf-upload` drop-zones with large upload icon badges, and consistent `.site-footer`, keeping all existing form control IDs intact.
- **Where**: `src/i_love_open_converter/templates/*.html` (18 dedicated tool templates)
- **Depends on**: T1, T2
- **Requirement**: UI-05, UI-06
- **Tests**: integration & e2e (`tests/test_conversion_coverage.py`, `tests/test_mobile_ui.py`)
- **Gate**: full

### T5: Full Test Suite Verification, GitHub Pull Request & Live Service Startup
- **What**: Run `ruff check`, `ruff format --check`, `pytest` (including Playwright E2E mobile/desktop tests), commit atomic changes, push branch `feat/ui-ilovepdf-experience`, update Pull Request #64 in English, and leave FastAPI web + worker services running for user verification.
- **Where**: Repository-wide & GitHub PR #64
- **Depends on**: T6, T7, T8
- **Requirement**: UI-01..UI-06
- **Tests**: full suite
- **Gate**: build

### T6: Bespoke Vector Icon System, Unclipped Chips & Instant Tool Search
- **What**: Equip all active PDF and Image catalog cards with custom semantic inline `<svg>` icons, allow category chips to wrap cleanly on desktop without clipping, and add an accessible instant search bar (`[data-catalog-search]`) to filter the 50 tools in real time.
- **Where**: `src/i_love_open_converter/templates/index.html`, `src/i_love_open_converter/static/css/app.css`, `src/i_love_open_converter/static/js/app.js`
- **Depends on**: T2, T3
- **Requirement**: UI-04, UI-06
- **Tests**: e2e (`tests/test_mobile_ui.py`)
- **Gate**: quick

### T7: Tactile iLovePDF Document Sheet Thumbnails, Per-File Batch Removal & Dynamic Workspace Icon
- **What**: Render non-raster selected files as miniature folded-corner paper sheets with format ribbons, add individual file removal (`[data-remove-index]`) in multi-file batches, and mirror the selected tool card's SVG icon inside `.converter-heading-icon`.
- **Where**: `src/i_love_open_converter/static/js/app.js`, `src/i_love_open_converter/static/css/app.css`
- **Depends on**: T6
- **Requirement**: UI-02, UI-03
- **Tests**: e2e (`tests/test_mobile_ui.py`)
- **Gate**: quick

### T8: Universal Drag-and-Drop & Brand SVG Across All 18 Dedicated Tool Templates
- **What**: Unify the SVG `.brand-mark` across all 18 `/tools/*.html` pages, move `pdf-translate.html`'s footer outside `<main>`, and add `/static/js/tool-shell.js` so every `.pdf-upload` drop-zone supports `dragover` visual state and file `drop` assignment.
- **Where**: `src/i_love_open_converter/static/js/tool-shell.js`, `src/i_love_open_converter/templates/*.html`
- **Depends on**: T4
- **Requirement**: UI-05, UI-06
- **Tests**: e2e (`tests/test_mobile_ui.py`)
- **Gate**: full

---

## Validation Tables

### Task Granularity Check
| Task | Scope | Status |
| --- | --- | --- |
| T1: Overhaul CSS Design System | 1 stylesheet (`app.css`) | ✅ Granular |
| T2: Redesign Home Catalog & Studio HTML | 1 template (`index.html`) | ✅ Granular |
| T3: Enhance Client Studio Logic & File Cards | 1 script (`app.js`) | ✅ Granular |
| T4: Unify 18 Dedicated Tool Templates | Cohesive header/dropzone/footer shell across tool templates | ✅ Granular |
| T5: Verification, PR & Live Service | Validation + Git/PR + Daemon startup | ✅ Granular |

### Diagram-Definition Cross-Check
| Task | Depends On (task body) | Diagram Shows | Status |
| --- | --- | --- | --- |
| T1 | None | Start node | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T1, T2 | T2/T3 → T4 | ✅ Match |
| T5 | T3, T4 | T4 → T5 | ✅ Match |
