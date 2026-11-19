# Project state

## Decisions

| ID | Decision | Rationale | Status | Date |
| --- | --- | --- | --- | --- |
| AD-001 | The application has no user authentication; anyone who can reach the self-hosted service may use it | The user explicitly requested a free, unauthenticated HomeLab/local service | active | 2026-11-19 |
| AD-002 | License the project under AGPL-3.0 | The user selected AGPL-3.0 to keep network-served modifications open | active | 2026-11-19 |
| AD-003 | Store conversion jobs in SQLite and input/output files on the local shared volume; a separate worker polls SQLite | Lightweight single-host deployment avoids a separate broker and external storage, matching the HomeLab target | active | 2026-11-19 |
| AD-004 | Use `pymupdf-lite` for the basic PDF toolchain | It retains the PyMuPDF API and AGPL path while omitting optional layout/OCR model dependencies from the base container, reducing image size and keeping basic operations local | active | 2026-11-19 |
