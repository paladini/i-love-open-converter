# Convert PSD to raster images

**Approved**: 2026-11-21 - user: “Pode seguir nas implementações dde acordo com o [$tlc-spec-lean](<C:\Users\Fernando Paladini\\.codex\\skills\\tlc-spec-lean\\SKILL.md>) até o final. Vá abrindo PRs conforme precisar e vá seguindo tudo da implementação”
**Settled mid-build:** none
**Review:** pending.
**Fix pass:** pending.

## Problem

The image catalog lists PSD conversion but cannot accept Photoshop documents. People who need a shareable image have to install a separate editor or use a hosted conversion service.

When this ships, a visitor can convert one supported static PSD into a flattened PNG, JPEG, or WebP image processed locally.

## Shape

The feature reuses the existing image upload, job queue, image form, artifact download, and expiry behavior. The API validates the PSD request before queueing, while PSD parsing, compositing, and raster output are exercised through the worker and its tests.

1. One PSD and a requested PNG/JPEG/WebP format enter `main.py` (exists), which validates request shape, file signature, document limits, and stores a queued `image.from_psd` job.
2. `worker.py` (exists) passes the stored source to `psd_ops.py` (new), which launches `psd_worker.py` (new) with parse/allocation, CPU, memory, file-size and filesystem limits, then composites visible content and writes a bounded output image.
3. The existing job status and download handlers return the result and localized errors.

```mermaid
flowchart LR
    A[1 main.py (exists): validate and queue] --> B[2 worker.py (exists): dispatch]
    B --> C[2 psd_ops.py (new): validate and isolate]
    C --> D[2 psd_worker.py (new): composite PSD to raster]
    D --> E[3 Existing status and download]
```

Data: none - reuse conversion jobs and artifacts; temporary files are not retained beyond normal job expiry.

**Changes underneath**

| Front | What changes |
| --- | --- |
| image operation | Add single-file `image.from_psd`, handled by API validation and worker dispatch. |
| PSD renderer | Use pinned `psd-tools` to read a document composite and Pillow to write PNG/JPEG/WebP; do not follow external linked smart objects. |
| worker isolation | Use the existing network-isolated worker and Landlock pattern for a per-document child, with bounded parsing and rendering. |
| image catalog and form | Enable the existing PSD catalog entry, one-file input, output selection, bounds, and PT-BR/English copy. |
| stored data | No schema or persisted-data changes. |
| readers | Existing job status and download routes expose the result. |

## Surface

| Route | In | Out | Status | Who |
| --- | --- | --- | --- | --- |
| `POST /api/jobs` (existing; new `image.from_psd`) | One PSD file up to configured 100 MB per-file limit, output format | Existing queued job response | `202`; `400` malformed multipart; `413` file too large; `415` unsupported extension; `422` invalid request, signature or PSD limits | anyone |
| `GET /api/jobs/{job_id}` (existing) | Job id | Existing job state | `200`, `404` unknown job | anyone |
| `GET /api/jobs/{job_id}/download` (existing) | Successful job id | One flattened raster image | `200`, `404` unknown job, `409` pending or failed | anyone |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| PSD parsing dependency | Pin `psd-tools[composite]==1.27.0`; retain its MIT notice through installed dependency metadata and project third-party notice | Reusing Pillow alone does not provide the required PSD layer composite API; the documented composite extra enables vector strokes, fills and supported layer effects. |
| Document bounds | One `.psd`, maximum 100 MB under existing upload settings, 8-bit RGB/grayscale documents, at most 40 megapixels; parse at most 100,000 objects/32 nested descriptors and 512 MiB cumulative reads; cap each render allocation at 512 MiB | Unbounded canvas/layer allocations can exhaust worker memory; broad color/depth compatibility is not reliable for a first pass. |
| Composite semantics | Render the merged visible composite to a flattened image, PNG/JPEG/WebP; preserve source transparency when present for PNG/WebP and flatten JPEG onto white | Exporting editable PSD layers is outside a raster conversion tool; claiming Photoshop-perfect output would exceed renderer support. |

- No database schema change, backfill, or API route is added.

## Criteria

### S1: Convert one bounded PSD to a flattened image locally (P1)

The existing PSD catalog entry becomes a working, bilingual local conversion flow.

**Acceptance Criteria**

1. WHEN a visitor selects “Converter de PSD” THEN the page SHALL offer one `.psd` upload, PNG/JPEG/WebP output, the 40 MP canvas limit, and the local-processing notice in PT-BR and English.
2. WHEN a visitor submits one supported PSD with a valid output format THEN the API SHALL queue exactly one `image.from_psd` job and the worker SHALL produce exactly one flattened raster image.
3. WHEN the source is RGB or grayscale at 8 bits per channel and no larger than 40 megapixels THEN the renderer SHALL composite the visible document canvas; PNG/WebP SHALL preserve source transparency when present and JPEG SHALL flatten transparent pixels onto white.
4. IF the file is missing, multiple files are submitted, the extension/signature is not PSD, the output format is invalid, the document is not a supported mode/depth, canvas area exceeds 40 megapixels, or file size exceeds 100 MiB THEN the API SHALL reject before creating a job.
5. IF a PSD is corrupt, cannot be composited, or contains a smart-object layer THEN the worker SHALL fail closed, expose no download, and remove partial output without reading linked paths.
6. WHEN a visitor submits the conversion, observes queued/failed/succeeded state, and downloads success at a 360 CSS-pixel viewport THEN the controls, statuses, errors, and localized output choice SHALL remain usable without horizontal page overflow.
7. WHILE a PSD is processed THEN the child renderer SHALL run under Landlock in the existing network-isolated Linux worker, SHALL not make network requests, and SHALL not open linked smart-object paths.

## Assumptions

| Decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Input count and size | Exactly one PSD up to existing 100 MB per-file limit | This is the catalog's single-document conversion path; the existing upload parser enforces the configured limit before spooling. | y - user delegated the complete roadmap and implementation choices |
| Output formats | PNG, JPEG, WebP | Reuses existing raster image output choices and local encoders. | y - user delegated the complete roadmap and implementation choices |
| PSD support | 8-bit RGB/RGBA/grayscale, max 40 megapixels | Bounded first implementation with modes supported by the image pipeline; unsupported PSD modes fail with a clear message. | y - user delegated the complete roadmap and implementation choices |
| Linked smart objects | Reject the document rather than resolve paths | A self-hosted worker must not read arbitrary local files. | y - user delegated the complete roadmap and implementation choices |

**Open questions:** none - the user delegated completion of the staged roadmap and implementation choices.

## Differences from the source

No binding screenshot or source UI was supplied. Reuse the existing catalog card and image form.

## Out of scope

- Editing or preserving PSD layers, PSB files, Photoshop-perfect rendering, linked smart-object resolution, color-management editing, CMYK/Lab/duotone/bitmap/indexed/multichannel modes, 16/32-bit documents, animated or multi-artboard exports, and batch PSD processing.

## Sources

- `.specs/features/project-foundation/plan.md` - approved staged roadmap and local processing constraints.
- `https://psd-tools.readthedocs.io/en/latest/usage.html` and `https://psd-tools.readthedocs.io/en/latest/reference/psd_tools.html` - `PSDImage.open`, `composite`, the documented allocation budget, and renderer limitations.
- `https://github.com/psd-tools/psd-tools/blob/main/LICENSE` - psd-tools MIT license.
