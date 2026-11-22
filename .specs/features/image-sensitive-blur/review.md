# Review

## Verdict: changes requested

The implementation follows the approved scope: it adds local plate detection and a separate manual-region blur path, keeps both operations on the existing job pipeline, and documents the detection limits. I reviewed the request sentence by sentence against the plan and code. The plan has no design captures, so there were no captured states to compare. I opened the running app at `http://127.0.0.1:8097/` and confirmed both tools appear in the catalog and are selectable; I did not upload a file or modify the running app's data.

## Findings

### [P2] Localize the preview's accessible names

`templates/index.html:166-168` gives the region editor and canvas fixed Portuguese `aria-label` values, with no `data-i18n-aria` translation keys. The visible instructions, counter, and buttons have English translations, but assistive technology still announces the preview as “Prévia da imagem para seleção de regiões” and the section as “Seleção de regiões” when English is selected. This falls short of criterion 9's bilingual preview and region controls. Add localized accessible-name keys and assert their values after switching languages.

### [P2] Add tests for the new operations' API rejection and detector wiring

The new region tests exercise rectangle validation and one successful API job (`tests/test_image_ops.py:458-466`, `tests/test_api.py:1383-1429`), while the new plate tests stub `_detect_plate_regions` (`tests/test_image_ops.py:469-493`, `tests/test_api.py:1432-1452`). The existing 40 MP and multiple-file API rejection test is for `image.blur_faces` (`tests/test_api.py:1455`), not either new operation. As a result, no test would fail if the new API stopped rejecting multiple files, unsupported plate inputs, invalid output formats, or images above 40 MP; likewise, the plate tests would pass if bundled cascade loading or detection were broken. Those are explicit rules in criteria 2 and 4 and the TLC test rule requires a test that fails when each rule is wrong. Add operation-specific API rejection tests and a detector-loading/integration check for the bundled cascades (without requiring a guaranteed plate detection on arbitrary photos).

## Evidence reviewed

- `image_ops.py:629-676` loads the two OpenCV cascades, downsizes the image, maps detected boxes back to the image, and validates bounded normalized regions.
- `image_ops.py:720-754` blurs selected regions and raises on an empty plate result.
- `main.py:758-763`, `1241-1260`, and `1726-1758` enforce the single-file contract, operation options, oriented 40 MP limit, and region validation before job creation.
- `worker.py:85-92` routes both tools through image processing; `worker.py:284-292` marks no-plate jobs failed and removes partial output.
- `app.js:471-542` draws and manages regions; `app.js:635-660` requires and sends selections. The source inspection shows normalized coordinates and clearing on a new file, but there are no browser-level tests for those interactions.
- The running app catalog exposed both new cards. The plan's `captures/` directory does not exist, so no visual source captures were supplied.

## Review limits

This was a static code/test review plus a read-only catalog check in the running app. I did not run the test suite or submit files, preserving the running app's data. No changes were made outside this `review.md` file.
