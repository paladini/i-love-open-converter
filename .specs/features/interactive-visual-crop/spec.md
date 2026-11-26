# Feature Specification: Interactive Visual Crop with Handles (`#65`)

**Issue:** [paladini/i-love-open-converter#65](https://github.com/paladini/i-love-open-converter/issues/65)
**Status:** Planned (GATE-PLAN)

## Problem Statement

Currently, cropping an image (`image.crop` in `index.html` / `app.js`) or cropping a PDF (`/tools/pdf-crop` in `pdf-crop.html` / `pdf-crop.js`) requires users to type numeric coordinates manually (`left`, `top`, `width`, `height` in pixels for images; `left`, `top`, `right`, `bottom` in percentages for PDFs). `image.crop` has no interactive crop preview, and `pdf-crop` only renders a static non-draggable `#crop-selection` box.

## Requirements

- **REQ-01 (Vendored Offline Library):** Vendor `Cropper.js` (`v1.6.x`, MIT license) locally in `src/i_love_open_converter/static/vendor/` (`cropper.min.js`, `cropper.min.css`), with zero external CDN or network requests, and document attribution in `THIRD_PARTY_NOTICES.md`.
- **REQ-02 (Interactive Crop Box):** Both `image.crop` and `/tools/pdf-crop` display an interactive crop box over the preview image with:
  - 8 resize handles (4 corners + 4 edges)
  - Whole-box dragging
  - Dimmed backdrop (scrim) outside the crop zone and rule-of-thirds grid lines inside
  - Touch gesture support on mobile and tablet viewports
- **REQ-03 (Aspect Ratio Presets):** Both tools provide aspect ratio preset buttons in the sidebar/controls: `Free`, `1:1`, `16:9`, `4:3` (localized in `en` and `pt-BR`), with active state indication.
- **REQ-04 (Bidirectional Sync — Image Crop):**
  - When `image.crop` is active and a previewable image is selected, instantiate Cropper on a dedicated crop stage image (`#image-crop-preview`) in `workspace-stage`.
  - Dragging/resizing the crop box updates `#crop-left`, `#crop-top`, `#crop-width`, `#crop-height` in natural pixel coordinates.
  - Editing `#crop-left`, `#crop-top`, `#crop-width`, `#crop-height` updates the Cropper box in real time (clamped to valid bounds).
  - Switching away from `image.crop` or removing/changing the file cleanly destroys the Cropper instance and revokes object URLs.
  - Multi-file batch uploads remain supported (previewing the first image as reference and submitting the shared pixel coordinates).
- **REQ-05 (Bidirectional Sync — PDF Crop):**
  - On `/tools/pdf-crop`, bind Cropper to `#preview` once the PDF page image finishes loading (`previewReady`).
  - Dragging/resizing updates `#left`, `#top`, `#right`, `#bottom` as percentages (`0–100`, rounded sensibly, with `left < right` and `top < bottom`).
  - Editing `#left`, `#top`, `#right`, `#bottom` updates the Cropper box in real time.
  - Navigating between PDF pages (`#previous` / `#next`) preserves/re-applies the current percentage crop box on the new page preview.
- **REQ-06 (Automated Verification):**
  - Playwright E2E tests covering both `image.crop` and `/tools/pdf-crop` on desktop and mobile viewports: handle rendering, drag/resize updating inputs, input changes updating Cropper box, aspect ratio presets, and job submission.
  - Existing `pytest` suite, `ruff check .`, and `ruff format --check .` pass.

## Out of Scope

- Backend coordinate schema changes (`image.crop` continues using `{left, top, width, height, format, quality}` in pixels; `pdf.crop` continues using `{rectangle: [l, t, r, b], ranges}` in `0..1` fractions).
- Per-file independent crop boxes for multi-image batch jobs.
- Image rotation/flip inside the crop UI (already handled by dedicated `image.rotate` / `pdf.rotate` tools).
