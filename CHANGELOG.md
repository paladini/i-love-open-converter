# Changelog

This changelog records user-facing changes included in each release.

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
