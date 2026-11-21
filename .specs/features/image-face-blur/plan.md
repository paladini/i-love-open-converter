# Blur faces in images

**Approved**: 2026-11-21 - user delegated completing the application roadmap and implementation choices under tlc-spec-lean.
**Settled mid-build:** none
**Review:** pending
**Fix pass:** pending review

## Problem

The image catalog shows face blurring as coming soon. Visitors need a local, one-image way to obscure detected faces before sharing a picture. A tool intended to protect privacy must clearly report when it cannot detect a face instead of silently returning the unchanged source.

## Shape

Reuse the existing image operation and job flow. Apply EXIF orientation before detection, cap the source at 40 megapixels, and run OpenCV CPU cascade detection locally. Combine frontal and profile detections, pad each face rectangle, and apply strong Gaussian blur to the covered region. Do not promise that every face will be detected.

1. The browser submits one supported static image and the new `image.blur_faces` operation to `POST /api/jobs`.
2. `main.py` validates image content and oriented dimensions before creating the existing local job record.
3. Existing `worker.py` uses the image processor and a cached OpenCV cascade detector for frontal and profile face regions, then writes the selected PNG/JPEG/WebP output.
4. If no face is detected, the worker records `no_faces_detected`; existing status and download routes expose the failure without an output artifact.

```mermaid
flowchart LR
  A[1 browser form and API request - existing] --> B[2 main.py - existing validation]
  B --> C[3 existing worker.py local image operation]
  C --> D[3 OpenCV Haar face cascades - new]
  D --> E[4 status and download routes - existing]
```

Data: none - use existing `conversion_jobs` and `job_artifacts`; no database schema change.

### Changes underneath

| Existing element | Change | Readers and consequence |
| --- | --- | --- |
| Image operation names | Add `image.blur_faces`; require one source | API, UI, and worker recognize the operation. |
| Image processor | Cache frontal/profile cascades and blur padded face rectangles | CPU processing stays on the self-hosted server; no model server or network call. |
| Job error codes | Add `no_faces_detected` | Worker fails closed for images with no detected faces; PT-BR and English show a localized explanation. |
| OpenCV dependency | Add pinned headless OpenCV package | No GUI libraries are installed; bundled cascade assets are used locally. |

## Surface

| Route | Input | Output | Status | Who |
| --- | --- | --- | --- | --- |
| `POST /api/jobs` (existing, new `image.blur_faces`) | One supported static raster image up to 40,000,000 oriented pixels; optional output format | Queued job | `202`, `422` invalid image/options/pixel cap, `415` unsupported extension | anyone |
| `GET /api/jobs/{job_id}` (existing) | Job id | Job status or `no_faces_detected` failure | `200`, `404` unknown job | anyone |
| `GET /api/jobs/{job_id}/download` (existing) | Successful job id | One face-blurred image | `200`, `409` processing/failure, `404` unknown job | anyone |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| Detector | CPU OpenCV frontal and profile Haar cascades, loaded from the pinned headless package | Cloud detection would transmit private images; GPU/model downloads would complicate local use. |
| Behavior | Fail the job when no face is detected; strongly blur padded detected face rectangles | Returning an unchanged image would falsely imply that the requested privacy action succeeded. |
| Scope | Faces only, one image, up to 40 MP; disclose detection limits and require result review | Claiming plate or arbitrary-object detection without detectors would be misleading. |

## Criteria

### S1: Blur detected faces locally (P1)

**Acceptance Criteria**

1. WHEN a visitor selects `Desfocar cara` THEN the page SHALL show one-image selection, localized PNG/JPEG/WebP output controls, a 40 MP limit, local processing disclosure, and a clear face-detection limitation in PT-BR and English.
2. WHEN a supported image contains a detected frontal or profile face THEN the local worker SHALL apply strong Gaussian blur to the padded detection region and return one selected-format image at the EXIF-oriented source dimensions.
3. WHEN the visitor uploads an image THEN the API and worker SHALL not send its content to an external service.
4. IF no face is detected THEN the job SHALL fail with a localized `no_faces_detected` message and SHALL NOT produce a downloadable output.
5. IF the request has zero/multiple files, unsupported content/extension, invalid output format, or more than 40,000,000 oriented pixels THEN the API SHALL return an appropriate 422/415 response before creating a job.
6. IF decoding or worker processing fails THEN the job SHALL fail without a partial output artifact.
7. WHEN the page is opened at 360 CSS pixels wide THEN its input and output controls SHALL remain reachable without horizontal page overflow.
8. WHEN a visitor reads the tool description or documentation THEN it SHALL state that detection can miss faces and that plates and arbitrary objects are not detected in this version.

## Out of scope

- License-plate or arbitrary-object detection, manual blur regions, batch processing, cloud inference, face recognition, and identity matching.
- Guaranteeing that every face is detected or treating the output as a substitute for human review.

## Assumptions

| Decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Detection | OpenCV Haar frontal and profile cascades | CPU-only, local, bundled pretrained classifiers; no model download at runtime | y - implementation delegated |
| Blur | Strong Gaussian blur over padded face rectangles | Simple processing with context margin around each detected face | y - implementation delegated |
| No detections | Fail closed with `no_faces_detected` | Avoid a successful download of an unchanged image from a privacy tool | y - implementation delegated |
| Source size | 40 million oriented pixels | Bounds decoded image memory in the worker | y - implementation delegated |
| Scope | Faces only | Plates and arbitrary objects require separate detectors or manual regions | y - first increment |

**Open questions:** none - implement the local face-only first version with these limits disclosed.

## Sources

- [OpenCV cascade classifier tutorial](https://docs.opencv.org/4.9.0/db/d28/tutorial_cascade_classifier.html) - documents `CascadeClassifier` and `detectMultiScale` face detection.
- [OpenCV project license](https://github.com/opencv/opencv/blob/4.x/LICENSE) - Apache-2.0 for OpenCV 4.x and later.
- [opencv-python-headless on PyPI](https://pypi.org/project/opencv-python-headless/) - headless Python package, Python 3.14 wheel availability, and current package metadata.
