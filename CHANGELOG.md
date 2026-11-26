# Changelog

This changelog records user-facing changes included in each release.

## [1.2.0] - 2026-11-26

### Added

- **Interactive visual crop (`image.crop` and `/tools/pdf-crop`):** vendored `Cropper.js` v1.6.2 locally for 100% offline visual cropping with 8 resize handles, dimmed scrim, rule-of-thirds guides, touch support, aspect ratio presets (`Free`, `1:1`, `16:9`, `4:3`), and bidirectional real-time synchronization with the existing numeric coordinate inputs.

## [1.1.0] - 2026-11-26

Substantial UI/UX Studio redesign inspired by iLovePDF and iLoveIMG, preserving 100% local, self-hosted operation.

### Added

- **Studio Workspace (`/`):** 2-column split Studio Workspace above the catalog with dynamic domain-adaptive OKLCH theming (Crimson Coral for PDF tools, Cobalt Indigo for Image tools), URL deep-linking (`?tool=`), and live active-tool SVG badge mirroring.
- **Visual file cards & batch controls:** live image thumbnail previews, folded-corner miniature document sheets with format badges (`PDF`, `RAW`, `PSD`, `HEIC`, `SVG`), tabular file sizes, `+ Add more` batch append button, per-file `×` removal, and `↑`/`↓` ordering for PDF merges.
- **Catalog discovery:** bespoke semantic inline SVG icons across all active PDF and image tools, unclipped wrapping category filter chips on desktop, and an instant client-side tool search bar.
- **Universal dropzone shell:** shared drag-and-drop highlight and file drop support (`tool-shell.js`) across all dedicated `/tools/*` pages.

### Changed

- Unified the sticky `.site-header` (brand SVG emblem, quick `PDF` / `Images` / `All` navigation shortcuts, `100% local` pill, and `EN` / `PT` language switcher) and `.site-footer` across all 19 HTML templates.
- Upgraded typography, contrast, `:focus-visible` outlines, `touch-action: manipulation`, and `360px` mobile responsiveness in accordance with Web Interface Guidelines.

## [1.0.0] - 2026-11-23

The first stable release. This release consolidates the changes shipped since v0.1.0.

### Added

- **PDF workflows:** local OCR, editable PDF form creation with local field suggestions, extractive and abstractive local summaries, offline Portuguese/English translation, selectable compression profiles, batch compression, and batch rotation.
- **PDF exports:** Word, PowerPoint, Excel, Markdown, and embedded-image exports. Scanned PDFs can use local OCR before Word or Excel export; Markdown and extracted images are packaged as ZIP files.
- **Web and document conversion:** convert local HTML and public URLs to PDF or images, and scan documents into PDFs. URL fetching is bounded to public HTTP(S) resources and the rendering worker remains offline.
- **Image formats and tools:** convert HEIC/HEIF, camera RAW, SVG, and PSD files locally; create animated GIFs from ordered JPEGs; blur plates and user-selected regions; and add sticker overlays in the photo editor.
- **Runtime reliability:** added native conversion smoke checks to container builds and expanded conversion-path, invalid-input, and job-matrix coverage. Added bounds and isolation for untrusted image and document processing.
- **Project documentation:** refreshed the English and Brazilian Portuguese READMEs, added screenshots and social preview artwork, and added community health and dependency update files.

### Changed

- Set English as the default interface language while retaining Brazilian Portuguese.
- Improved local PDF summary generation and PDF/image batch workflows.
- Updated the container build to include the local summary model and runtime conversion checks.

### Fixed

- Hardened temporary-file access, upload limits, image decoder resource use, document conversion isolation, and public URL validation.
- Allowed isolated workers to load packages from the active Python environment while keeping their filesystem rules limited to that runtime and each job's temporary directory.
- Addressed conversion edge cases found during feature reviews, including image allocation limits, PDF summary ranking, and editor overlays.
