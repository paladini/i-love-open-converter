# Review

**Reviewer verdict: changes required before merge.** The author completed the single fix pass: the composition, validation-boundary and cleanup regression gaps below were covered. Focused tests and the full repository suite pass after those changes. No second review was run, as required by the skill.

## Evidence

- Read `.specs/features/image-watermark/request.md` sentence by sentence and compared the request with the plan, API validation, worker dispatch, Pillow composition, UI and README.
- No capture files exist in `.specs/features/image-watermark/captures/`. Started the home page at `http://127.0.0.1:8779/` with a throwaway `DATA_DIR` at `.specs/features/image-watermark/review-data/`. At 360 px, selected Watermark image and inspected Text and Image modes in PT-BR and English. Both modes expose the relevant text/file, nine-position, opacity and output controls; the page content fits the viewport without horizontal page overflow. The file input is marked required in image mode by `syncWatermarkControls()`.
- Ran `rtk proxy uv run pytest -q tests/test_image_watermark.py`: 9 passed.
- The existing tests assert a visible text mark at bottom-right, an ordered two-file ZIP that excludes the overlay, 10% overlay opacity for an opaque mark, and rejection of blank text, unknown position, opacity below 10, missing overlay and TIFF overlay extension. They also check that the job table remains empty for those validation failures.
- Stopped the review server and removed the temporary review database. No application data outside the disposable review directory was changed.

## Findings

### [P2] Assert the full image-watermark composition contract

`tests/test_image_watermark.py:35-110` does not protect several guarantees in acceptance criteria 2, 5-7. The text test uses opacity 100 only and does not exercise EXIF orientation. The overlay batch test checks the mark's pixel only in the first result; the second result's dimensions alone would still pass if its overlay were omitted. Both overlay fixtures are fully opaque, so neither checks preservation of the overlay's own alpha. No test asserts overlay aspect ratio, the 25%-of-short-side maximum, no enlargement, or placement on both different source sizes. Add focused tests whose pixel/dimension assertions fail if these properties regress.

### [P2] Cover watermark validation and failed-job cleanup at the boundaries

The API tests at `tests/test_image_watermark.py:115-149` omit text longer than 120 characters, opacity above 100, unsupported output format, duplicate overlay fields, malformed overlay data, and an overlay exceeding the configured image-pixel bound. They also do not exercise a source failure after an earlier batch output has been produced and assert that the failed job has no download. The implementation appears to validate these inputs and the worker removes the output directory on processing errors, but the current tests would not catch regressions in those explicit plan rules. Add API/job-level checks for these cases, including no job creation for pre-queue validation and no downloadable artifact for worker failures.

## Fix-pass scope

The findings are test gaps against explicit plan criteria. The inspected implementation appears to apply the tested text/image modes correctly, and the responsive localized UI worked in the reviewed states. No code or running application data was changed during this review; only this report was added.
