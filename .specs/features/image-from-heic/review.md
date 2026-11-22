# Review

**Verdict:** Request changes. The HEIC flow is present and the checked UI state is usable at 360 CSS pixels, but the child process has filesystem permissions outside the allowlist approved in the plan.

## Request and screen

The request records the user's direction to continue the local, self-hosted image/PDF converter and the approved HEIC slice. The slice replaces the coming-soon HEIC entry with HEIC/HEIF-to-JPEG conversion; RAW remains a separate stage. The implementation adds the catalog operation, upload validation, worker conversion, and JPEG download path.

I opened the running app read-only at 360×800. The initial page and selected HEIC tool both measured `clientWidth=360` and `scrollWidth=360`. Selecting the tool showed `Converter de HEIC`, accepted `.heic,.heif,.hif`, selected JPEG, and displayed the local-processing note. Switching to English showed `Convert from HEIC` and the translated note. The page returned HTTP 200 and produced no page errors. I did not submit a job or change the running app's data. There is no captures directory, so there were no binding captures to compare.

## Findings

### [P2] The HEIC child receives permissions on shared `/tmp`

The plan at `plan.md:66` limits Landlock access to the per-job temporary root and required application files. `heic_worker.py:82` calls the shared `restrict(root, allow_app=True)` helper, whose `/tmp` rule at `src/i_love_open_converter/office_sandbox.py:45` grants `REMOVE_FILE` and `MAKE_SOCK` to the whole shared `/tmp` directory. It grants no read permission there, so this does not enable reading neighboring files, but a compromised decoder can remove a known file in `/tmp` outside its job root. That is broader than the approved allowlist. Add a HEIC-specific restriction that omits those `/tmp` permissions (while preserving any Office-specific behavior), and cover the effective restriction with a Linux test.

The current child test helper replaces `restrict` with a no-op at `tests/test_heic_ops.py:276`; therefore the HEIC tests would still pass if Landlock were removed or granted broader rights. The live worker reports Docker network mode `none` and `OFFICE_NETWORK_ISOLATED=1`, which supports the network-isolation part of the criterion.

## Acceptance-criteria evidence

1. **Catalog and localized limits:** `test_heic_catalog_and_form_are_available_in_both_languages` checks both title strings and the note. The read-only 360px browser check confirmed selection, accepted extensions, JPEG output, and no horizontal overflow in PT-BR and English.
2. **Single and batch output:** `test_heic_api_queues_supported_extensions_with_jpeg_output`, `test_heic_api_defaults_to_jpeg`, and `test_heic_api_and_worker_return_one_jpeg_or_a_zip_for_batches` cover the API/worker path. The last test stubs the native converter, so it does not prove the real binary result; the builder's separate smoke run is outside this review.
3. **Extension and brand rejection before job creation:** `test_heic_api_rejects_unsupported_uploads_before_creating_job` checks status, error code, and zero created jobs. The API also checks the 100 MiB cap in `main.py:1534`, but this limit has no direct API boundary test.
4. **Single primary decode, output options, metadata flags:** `test_heic_child_caps_info_output_and_decodes_a_single_primary_image` checks the primary-image path, quality 92, white composition option, omitted EXIF/XMP extraction flags, and resource limits. It stubs both decoder calls and does not test output pixels, metadata, transparency, or orientation. The pinned libheif decoder's default decoding options apply transformations (`ignore_transformations` defaults to false in upstream `heif_decoding.h`), and this invocation does not override that default, but no rotated-image fixture would catch a regression.
5. **Invalid dimensions, sequences, failures, and resource bounds:** `test_heic_child_rejects_extra_images_sequences_and_oversized_dimensions` covers an extra image, a sequence, and a side above 32,768 pixels. `test_convert_heic_maps_child_failures_and_removes_partial_output` covers error mapping and partial-output cleanup; the valid-child test asserts the 3 GiB, 120 CPU-second, and output-size limits are set. Zero dimensions, the 40 MP boundary, corrupt/truncated inputs, timeout behavior, and an over-limit output are not exercised directly.
6. **Per-file isolation and network:** the child calls the Landlock helper and the running worker is network-isolated, but no HEIC test exercises the real Landlock rules; the mock at `tests/test_heic_ops.py:276` means a missing or widened filesystem rule would not fail this suite. The `/tmp` permissions above need correction.
7. **360px interaction:** the read-only browser check confirms the initial and selected-tool states do not overflow and the control is usable. No job was submitted to the existing app, so queued/failed/succeeded states were not visually exercised here; the API/worker test checks queued-to-success output behavior without a browser.

## Fix pass

The HEIC child now omits the shared `/tmp` Landlock rule and switches to its private working directory before applying Landlock, then passes relative input and output names to the decoder. The shared helper retains its existing `/tmp` permission by default for other operations. A Linux regression test confirms the HEIC policy blocks deleting a neighboring temporary file and creating a socket outside the per-file root. An API boundary test confirms uploads above the native decoder's byte limit are rejected before job creation.

Verification after the fix: the focused HEIC suite passed on Windows (30 passed, 5 Linux-only skips); the filesystem-restriction probe passed on Ubuntu; Ruff and changed-file formatting passed; the updated Docker image built and converted the synthetic HEIC with network disabled to a 640×480 JPEG with the expected pixel and no EXIF. A full Linux test run in the bridge-networked container ended with four PSD end-to-end cases failing to produce output; the PSD module then passed all 17 tests by itself. The failures are recorded for CI confirmation.

