# Blur plates and selected image regions

**Approved**: 2026-11-21 - user: “Sim, placas automáticas + objetos por seleção manual (Recomendado)”
**Settled mid-build:** none
**Review:** sent at 6e80f94.
**Fix pass:** done - localized preview accessible names and added operation-specific API rejection plus bundled-cascade integration coverage.

## Problem

The image toolbox has no local way to hide license plates or selected sensitive objects. People must use an external editor or share an image with identifying details visible. Automatic plate detection can miss a plate, so visitors need a clear scope and must inspect the result.

When this ships, visitors can ask the local worker to blur plates its bundled OpenCV classifiers detect, or preview an image and draw regions over objects they choose to hide.

## Shape

1. The visitor selects a single image, chooses “Desfocar placas” or “Desfocar objetos,” and submits the existing upload form (`static/js/app.js` exists). In object mode, the visitor draws up to 20 rectangular regions on an oriented browser preview; the page sends those normalized coordinates with the image.
2. `main.py` (exists) validates one supported static raster image, the 40-megapixel oriented limit, output format, and—on object jobs—the normalized region list, then creates the existing local job.
3. `worker.py` (exists) calls `image_ops.py` (exists) to decode the EXIF-oriented image. Plate jobs detect with bundled OpenCV cascades, pad and blur detections, and fail if no plate is found. Object jobs blur each validated rectangle. Both write one selected PNG, JPEG, or WebP image.
4. Existing status and download routes (exist) report job state and expose only successful output; failed jobs remove partial output and use localized error messages.

```mermaid
flowchart LR
    A[1 Existing image upload form] --> B[2 main.py - existing API]
    B --> C{3 worker.py and image_ops.py - existing worker}
    C -->|plate mode| D[3 Bundled OpenCV plate cascades (door 2)]
    C -->|object mode| E[1 app.js (exists): visitor-drawn regions]
    D --> F[4 Existing status and download]
    E --> F
```

Data: none - reuse conversion jobs and artifacts; object coordinates exist only in job options and are removed with the normal job-retention cleanup.

### Changes underneath

| Existing element | Change | Readers and consequence |
| --- | --- | --- |
| Image operations in `main.py`, `image_ops.py`, and `worker.py` | Add `image.blur_plates` and `image.blur_regions`; keep each operation one-file and local | API and worker dispatch these tool names and validate their operation-specific options. |
| Image catalog in `templates/index.html` and `static/js/app.js` | Replace the plate and object “coming soon” cards with selectable tools; show a preview and region controls for object mode | Visitors can run the tools from the existing bilingual image form. |
| Job options | Keep normalized object rectangles per job, bounded to 20 entries | The worker consumes coordinates; the existing status response exposes no region data. |
| Conversion jobs and artifacts | No schema change | Existing job status, output cleanup, download, and expiry behavior remain the readers. |
| OpenCV package and notices | Reuse the pinned headless dependency and its bundled cascades | No new model service, downloaded asset, or runtime dependency. |

## Surface

| Route | Input | Output | Status | Who |
| --- | --- | --- | --- | --- |
| `POST /api/jobs` (existing; new `image.blur_plates` and `image.blur_regions` operations) | One image, selected format, and 1–20 normalized rectangles for region mode | Existing queued job response | `202`; `422` invalid image, dimensions, options or selection; `415` unsupported image | anyone |
| `GET /api/jobs/{job_id}` (existing) | Job id | Existing job state, with `no_plates_detected` on plate detection failure | `200`, `404` unknown job | anyone |
| `GET /api/jobs/{job_id}/download` (existing) | Successful job id | One blurred image | `200`, `404` unknown job, `409` failed or pending job | anyone |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| Operation contracts | `image.blur_plates` accepts one image and format; `image.blur_regions` accepts one image, format, and 1–20 normalized `{x,y,width,height}` rectangles in the EXIF-oriented image coordinate space | Reusing one operation with mode-dependent ambiguous fields makes validation and worker dispatch harder to reason about. |
| Automatic plate detection | Use the license-plate cascades bundled with pinned OpenCV; downscale for detection, map back to oriented pixels, pad and strongly blur detections, and fail with `no_plates_detected` if none are found | External or runtime-downloaded inference would add network/model-management costs; claiming detection certainty would be misleading. |
| Manual object regions | Browser-drawn rectangles, minimum four oriented pixels per side, maximum 20, strong Gaussian blur, and an explicit preview/review step | Automatic object recognition was not selected; manual regions only protect what the visitor marks. |
| Image bound | One static raster image up to 40 million oriented pixels; return one PNG, JPEG, or WebP image | Batch processing and unrestricted dimensions are outside the chosen tool size and exceed this privacy workflow. |

## Criteria

### S1: Blur detected license plates locally (P1)

**Acceptance Criteria**

1. WHEN a visitor selects “Desfocar placas” THEN the page SHALL show a single-image input, a format choice, the 40 MP limit, a local-processing notice, and a PT-BR/English warning that detection can miss plates and the result needs review.
2. WHEN a visitor submits one supported image THEN the API SHALL create one `image.blur_plates` job and the worker SHALL strongly blur padded plate detections from its bundled local OpenCV cascades while preserving EXIF-oriented image dimensions.
3. IF the plate detector finds no regions THEN the job SHALL fail with `no_plates_detected`, the page SHALL explain that no plate was detected, and no download SHALL be available.
4. IF a plate request has zero or multiple files, unsupported content or extension, an invalid output format, or more than 40 million oriented pixels THEN the API SHALL reject it before creating a job.

### S2: Blur visitor-selected object regions (P1)

5. WHEN a visitor selects “Desfocar objetos” and chooses an image THEN the page SHALL show the EXIF-oriented image preview and a region count; drawing a rectangle SHALL add it, removing a region SHALL remove only that region, and clearing regions SHALL leave none selected.
6. WHEN a visitor submits object mode with valid rectangles THEN the browser SHALL send normalized `{x,y,width,height}` values relative to the oriented image, and the worker SHALL strongly blur exactly those areas in one output image at the source's oriented dimensions.
7. IF object mode has no selection, more than 20 rectangles, a malformed rectangle, a rectangle outside the image, or a side under four oriented pixels THEN the page or API SHALL reject submission before creating a job and SHALL show a localized validation message.
8. WHEN the visitor replaces the selected image THEN the page SHALL clear old preview regions before showing the new image.

### Shared

9. WHEN either tool is used in PT-BR or English at a 360 CSS-pixel viewport THEN the upload, mode controls, disclosure, preview and region controls, status, error, and download SHALL be localized and usable without horizontal page overflow.
10. WHILE either job runs THEN the source image SHALL remain in the self-hosted service; no external inference endpoint or runtime model download SHALL receive image content.
11. IF image decoding, detection, or rendering fails THEN the worker SHALL fail the job and remove partial output so no download is exposed.

## Assumptions

| Decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Automatic detection | Use both license-plate cascades bundled with OpenCV; fail if neither detects a plate | Reuses local assets; an unchanged image must not look like a successful privacy operation | y - user approved automatic plate detection and delegated implementation choices |
| Manual regions | Draw up to 20 rectangles with pointer input; minimum side is 4 oriented pixels; overlapping regions are allowed | The user chose manual rectangular object selection and preview; normalized values work across display sizes | y - user chose manual rectangular object selection with preview |
| Blur | Use strong Gaussian blur, padded for detected plates and bounded by selected object rectangles | Simple local treatment with a visible result to review | y - user delegated implementation choices |
| Empty automatic detection | Fail with `no_plates_detected`; never return the unchanged source as success | Prevents an unchanged output from implying a detected privacy action | y - user delegated implementation choices |

**Open questions:** none - the user selected local automatic plate detection and manual object regions with a preview.

## Differences from the source

No binding screenshot or source UI was supplied. Use the existing image catalog and upload form.

## Out of scope

- Automatic object recognition, changes to face blur, batch jobs, video, cloud inference, stored region coordinates, and guaranteed anonymization.
- Plate detection guarantees. Visitors are told to review detections; manual region mode protects only the rectangles they select.

## Sources

- `.specs/features/project-foundation/feature-inventory.md` - remaining image catalog items and current feature state.
- `.specs/features/image-face-blur/plan.md` - local image job, error, size-limit and bilingual UI conventions.
- The pinned `opencv-python-headless==4.14.0.94` distribution includes its Haar cascade files; this plan adds no image dependency or external model archive.
