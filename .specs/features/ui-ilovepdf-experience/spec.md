# iLovePDF & iLoveIMG Experience Redesign Specification

## Problem Statement

While **I Love Open Converter** supports 50 self-hosted PDF and image tools, its visual hierarchy and workspace interaction diverge from the intuitive flow users expect from **iLovePDF** and **iLoveIMG**:
1. On the home page (`/`), selecting one of the 24 in-page tools updates `#converter-panel` buried beneath a 50-card grid without guiding the user to the workspace or visually differentiating PDF tools from Image tools.
2. Selected files are displayed as plain text list items rather than visual file cards with live image thumbnails, format badges, and clear batch controls.
3. Dedicated tool routes (`/tools/*`) use inconsistent headers, lack unified navigation or footers, and contain Web Interface Guidelines issues (`Inter` fallback font, tiny 8px–10px text sizes, plain text card badges instead of semantic vector icons, and missing drag-and-drop highlight feedback).

## Goals

- [x] Establish a cohesive **"Warm Editorial Utility"** aesthetic with domain-adaptive theming: signature **Crimson Coral** (`oklch(59% 0.21 24)`) for PDF tools (matching iLovePDF) and **Cobalt Indigo** (`oklch(54% 0.21 268)`) for Image tools (matching iLoveIMG).
- [x] Transform the home converter panel into an iLovePDF/iLoveIMG-style **2-Column Studio Workspace** (Visual File/Preview Stage on the left + Sticky Options & Primary Action Sidebar on the right) with instant search, domain filtering, and deep-linked tool selection (`?tool=...`).
- [x] Upgrade file selection to render visual **File Cards** with live image thumbnails (`URL.createObjectURL`), format badges, tabular file sizes, and batch reordering/removal controls.
- [x] Unify the top navigation header, upload drop-zones, drag-and-drop feedback, and footer across `index.html` and all 18 dedicated `/tools/*` templates while preserving 100% compatibility with existing API, form inventory, and Playwright E2E tests.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Backend conversion logic changes | All 50 operations and worker pipelines are already implemented and verified. |
| Cloud storage integrations (Google Drive / Dropbox) | Excluded by design to keep all file transfers 100% local and self-hosted. |
| External CDN fonts or analytics | Must remain 100% offline/self-hosted with zero `https://` asset requests in HTML templates. |

---

## User Stories

### P1: iLovePDF & iLoveIMG Studio Workspace & Visual File Cards ⭐ MVP

**User Story**: As a self-hosted user converting PDFs or images, I want a focused 2-column Studio Workspace with domain-specific color theming (PDF Crimson vs. Image Cobalt), visual file cards with live image thumbnails, and a prominent action sidebar so that interacting with any tool feels as immediate and intuitive as iLovePDF and iLoveIMG.

**Why P1**: Core interaction model requested by the user.

**Acceptance Criteria**:

1. WHEN a user selects a PDF tool or Image tool on `/` THEN the workspace (`#converter-panel`) SHALL switch its domain theme (`data-domain="pdf"` or `data-domain="image"`), update the URL query (`?tool=<op>`), and smoothly bring the workspace into focus.
2. WHEN a user selects or drops one or more files in `#convert-form` THEN `#selected-file-name` SHALL render visual file cards containing a live thumbnail preview (for raster images) or format badge (for PDF/RAW/PSD/HEIC/SVG), the filename, tabular file size, reorder controls (`↑`/`↓` for `pdf.merge`), and an `"Add more files"` trigger when batch upload is supported.
3. WHEN a conversion job succeeds THEN `#job-result` SHALL display a celebratory completion banner with filename, size comparison badge (for compression tools), high-contrast download button, and reset action.
4. WHEN viewed at `360px` mobile width or `1280px` desktop width THEN the workspace SHALL have zero horizontal overflow (`document.documentElement.scrollWidth === window.innerWidth`).

**Independent Test**: Run `uv run pytest tests/test_mobile_ui.py` and verify conversion flow at 360px and 1280px.

---

### P1: Scannable Catalog with Vector Badges, Domain Tabs & Quick Navigation ⭐ MVP

**User Story**: As a user exploring the 50 tools, I want a clean top navigation bar, instant category/domain filtering, and distinct vector icons on every tool card so that I can locate any PDF or Image tool in seconds.

**Why P1**: Mirrors the homepage discovery experience of iLovePDF and iLoveIMG.

**Acceptance Criteria**:

1. WHEN the home page loads THEN all 50 `.tool-card` elements SHALL display distinct color-coded icon containers with readable titles (14px–15px) and 2-line descriptions (12px) without tiny 8px–9px illegible text.
2. WHEN a user clicks a category chip or top navigation domain link (`PDF`, `Images`, `All Tools`) THEN the catalog SHALL filter or navigate smoothly and update active states.
3. WHEN inspected by automated contract tests THEN `index.html` SHALL contain zero external `https://` links, exactly 50 `.tool-card` elements, and all expected `data-tool` and `data-i18n` attributes.

**Independent Test**: Run `uv run pytest tests/test_api.py -k test_home_page_has_image_and_pdf_groups_and_local_assets`.

---

### P2: Unified Navigation, Dropzones & Web Interface Guidelines Across Dedicated Tool Pages

**User Story**: As a user navigating to dedicated PDF/HTML/Office tools (`/tools/*`), I want the same polished header, drag-and-drop upload card, focus states, and bilingual switcher as the home page.

**Why P2**: Ensures visual and interactive consistency across the entire application.

**Acceptance Criteria**:

1. WHEN a user visits any `/tools/*` route THEN the page SHALL render the unified `.site-header` with brand mark, quick navigation links, `100% local` badge, and language selector.
2. WHEN a user interacts with any control via keyboard or touch THEN `:focus-visible` outlines, `touch-action: manipulation`, and `aria-live="polite"` status regions SHALL comply with Web Interface Guidelines.
3. WHEN `test_every_form_option_is_inventoried_and_points_to_a_tested_operation` runs THEN every `<input>`, `<select>`, and `<textarea>` ID across all 19 templates SHALL match the tested inventory without regression.

**Independent Test**: Run `uv run pytest tests/test_conversion_coverage.py`.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| UI-01 | P1: Domain-adaptive OKLCH theme (PDF Crimson / Image Cobalt) & typography | Design | Verified |
| UI-02 | P1: 2-Column Studio Workspace (`#converter-panel`) with Stage + Options Sidebar | Design | Verified |
| UI-03 | P1: Visual File Cards with live image thumbnails, format badges, and batch controls | Design | Verified |
| UI-04 | P1: Scannable 50-card catalog with SVG badges and responsive grid | Design | Verified |
| UI-05 | P2: Unified `.site-header`, dropzones, and footer across all 18 `/tools/*` pages | Design | Verified |
| UI-06 | P2: Web Interface Guidelines compliance (focus-visible, reduced-motion, 360px layout, tabular-nums) | Design | Verified |
