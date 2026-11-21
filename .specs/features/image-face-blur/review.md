# Review: blur faces in images

**Verdict:** Changes requested. The core flow and fail-closed behavior match the request, but one explicit user-facing acceptance criterion is missing.

## Finding

- **[P2] Disclose the 40 MP limit in the selected tool UI.** The API rejects an oriented image above 40,000,000 pixels in `src/i_love_open_converter/main.py:1304-1319`, but neither localized selected-tool hint in `src/i_love_open_converter/static/js/app.js:22,66` nor the selected-tool note in `src/i_love_open_converter/templates/index.html:172` mentions that limit. On the running page, the upload hint says only “up to 100 MB”; the 40 MP restriction is therefore discoverable only after an upload fails. Criterion S1.1 explicitly requires the 40 MP limit to be shown.

## Request and criteria check

- The source request asks to activate the existing face-blur card and blur faces locally. `image.blur_faces` is wired through the page, API, worker, and image processor. The image catalog card is enabled.
- The first-version scope is face-only using local OpenCV Haar cascades. The implementation loads frontal and profile classifiers from `cv2.data.haarcascades`, also checks mirrored profile faces, pads detections, and applies Gaussian blur. The UI and both READMEs disclose that detection can miss faces and does not handle plates or arbitrary objects.
- **S1.1:** The running UI exposes a single-file input, PNG/JPG/WebP choices, local-server disclosure, and the limitations in PT-BR and English. It does not disclose the 40 MP cap (finding above). There are no capture files in `.specs/features/image-face-blur/captures/`, so there were no captured states to compare. The explicit 360 CSS-pixel condition was not independently exercised during this review.
- **S1.2:** `tests/test_image_ops.py:374-410` checks that a detected region is blurred and output dimensions follow EXIF orientation. These tests replace the detector with a known rectangle, so they test blur and orientation but would not fail if cascade detection stopped recognizing frontal/profile faces. Selected-format coverage is not specific to this operation.
- **S1.3:** The worker calls the local `process_image` path and OpenCV; no external inference call was found in the implementation. No network-transmission test exists.
- **S1.4:** `tests/test_image_ops.py:413-422` checks no-detection raises and creates no file; `tests/test_api.py:1358-1376` checks the job becomes failed, reports `no_faces_detected`, and has no output/download. The error code is mapped to both localized messages in the front-end dictionary.
- **S1.5:** `tests/test_api.py:1379-1401` checks multiple-file and >40 MP requests are rejected before a job is created. The generic image API tests cover invalid content and unsupported extensions for `image.convert`; there is no direct invalid-output-format or zero-file test for `image.blur_faces`. Shared API validation currently includes the new operation in the image-operation set and applies the common checks.
- **S1.6:** The processor raises on an over-limit image and the worker's general failure path removes the output directory. The new no-face worker test covers the privacy-specific failure path; no blur-specific malformed-image/processing-failure API test was added.
- **S1.7:** No 360 CSS-pixel capture or browser check was available in the feature captures, so this condition remains unverified by this review.
- **S1.8:** The selected-tool warning and README entries in English and PT-BR state the detector can miss faces and excludes plates/arbitrary objects.

The app was inspected at `http://127.0.0.1:8796/` in its existing process. I selected the tool and checked both languages; I did not upload a file or alter application data. No captures were supplied, and this review made no repository changes other than this report.

## Author response and fix pass

The P2 finding is fixed: both localized selected-tool hints now disclose the 40 MP limit, and `tests/test_api.py` asserts both strings. The full test suite, Ruff, JavaScript syntax check, and `git diff --check` pass after the change. The 360 CSS-pixel visual condition remains unverified: neither captures nor an independently controllable viewport were available in the review environment.
