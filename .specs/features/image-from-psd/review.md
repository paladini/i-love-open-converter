# Review

**Verdict: Changes requested.** The PSD flow is present and the browser flow worked with mocked job responses at 360 CSS pixels. The renderer does not meet the approved 512 MiB per-allocation bound at the 40 MP limit, and several acceptance rules have no regression test that would fail if the rule were removed.

## Findings

1. **[P1] The composite can allocate more than the 512 MiB render cap.** The plan caps each render allocation at 512 MiB (`plan.md:56`). The renderer accepts 40,000,000 pixels (`psd_ops.py:15,70`) and passes `512 MiB` to `PSDImage.open` (`psd_worker.py:13,31`), then calls `psd.composite` (`psd_worker.py:41`). I inspected the installed, pinned psd-tools 1.27.0 in the running worker: for an RGB composite with transparency, its `composite_pil` appends the alpha plane using `numpy.concatenate` without that allocation budget. At 40 MP, the resulting four-channel float32 array is 640,000,000 bytes (about 610 MiB), above the stated cap. The child process has a 2 GiB address-space limit, so this allocation is not stopped by the 512 MiB setting. The current implementation therefore does not enforce the approved per-allocation bound.

2. **[P2] Several acceptance rules are not protected by tests that would fail if they regressed.** See the criterion-by-criterion coverage below. In particular, the current tests do not exercise the real worker's smart-object rejection or Landlock setup, nor do they verify the exact job/artifact count or grayscale success path.

## Acceptance-Criterion Test Coverage

| Criterion | Test evidence and whether it would catch a wrong rule |
| --- | --- |
| 1 | `test_psd_tool_is_available_in_catalog_and_single_file_form` (`tests/test_psd_ops.py:236-244`) checks the card and two copy strings. It would catch a missing card/title, but not a multiple-file input, wrong visible format choices, missing 40 MP/local notice, or broken PT-BR/English form. The current browser form did expose a single `.psd` input, PNG/JPEG/WebP, the limit, and local-processing copy in both languages. |
| 2 | `test_psd_conversion_creates_one_bounded_raster_artifact` (`tests/test_psd_ops.py:95-130`) covers all three formats, job operation, dimensions, and downloaded image content. It does not assert the database row count or the status response's artifact count, so it would pass if extra jobs or artifacts were also created. |
| 3 | The same conversion test verifies an RGB composite, transparent PNG/WebP pixels, and white JPEG flattening. It does not construct a supported grayscale PSD or a hidden layer, so it would not catch rejection of grayscale input or compositing hidden content. |
| 4 | `test_invalid_psd_request_is_rejected_before_job_queue`, `test_psd_requires_exactly_one_file`, and `test_psd_upload_over_configured_file_limit_is_rejected_before_queue` (`tests/test_psd_ops.py:133-189`) cover bad extension/signature, unsupported mode/depth, >40 MP, invalid format, missing/multiple files, upload size, and no queued job. These assertions would fail for the tested gates. |
| 5 | `test_truncated_psd_fails_without_download_or_partial_output` (`tests/test_psd_ops.py:221-233`) checks corrupt-input failure and output removal. `test_smart_object_layers_are_detected_without_reading_linked_contents` (`:192-207`) tests only the helper with fake layers; it would still pass if the worker stopped calling that helper, and it does not prove a linked path is never opened. |
| 6 | There is no responsive-browser regression test. The catalog test is static. I used the running app with mocked POST/status responses: queued, failed, and succeeded states rendered; the success link was set; PT-BR and English copy rendered; and the root page had no horizontal overflow at the 360 CSS-pixel viewport. The attempted browser download navigation escaped my route stub and reached the app with the fake job id (404); the browser download action itself is therefore unverified here. The conversion test does assert a successful API download response. |
| 7 | `test_psd_renderer_requires_isolated_linux_worker` (`tests/test_psd_ops.py:210-218`) only checks that a false `office_isolated()` prerequisite fails closed. It does not exercise the child `restrict()` call, verify the worker's network isolation, or assert no linked-path access. Removing those protections would not make this test fail. |

## Screen and Scope

The feature folder contains only `request.md` and `plan.md`; `.specs/features/image-from-psd/captures/` is absent, and no capture files are tracked. I could not compare capture-by-capture states or sizes. I did inspect the supplied running instance at 360 CSS pixels. The form's visible output choices were PNG, JPEG, and WebP; `multiple` was false; PT-BR and English copy and queued/failed/succeeded states were usable; `document.documentElement.scrollWidth` equaled `clientWidth` (345 px with the browser scrollbar). POST and status requests were stubbed in the browser, so the app database was not changed. The fake download navigation returned 404 as described above.

The reviewed feature commit is `d064cd1` on `feat/image-from-psd`, after base `4b8d8b50da0369eadcf54c48cabcc99b9169264e`. I did not change feature code or commit. The working tree had the builder's uncommitted `plan.md` review-marker change; I left it untouched. No browser data or application records were written.

## Builder fix pass

The allocation issue is fixed. Layered documents now use 4096-by-4096 viewports, which keeps the compositor's largest four-channel float32 tile at 256 MiB; `psd-tools` retains its 512 MiB allocation guard. Layerless documents decode their existing merged composite with `topil()`, whose pinned allocation model admits the 40 MP RGB case. The child address-space ceiling now matches the worker's 3 GiB container memory limit; the lower 2 GiB ceiling rejected a valid 40 MP layered document before rendering.

Regression coverage now includes grayscale output, hidden-layer exclusion, exactly one job and output artifact, tile seam stitching, layerless merged data, smart-object rejection before compositing, Landlock before PSD parsing, and the worker's `network_mode: none` deployment. The UI test checks the single-file PSD input, format choices, bilingual limit copy, and flattening note. The complete suite passes with 404 tests.

I did not add a browser automation stack because this repository has no browser-test dependencies or browser CI setup. The independent review used stubbed queued, failed, and succeeded states at 360 CSS pixels; the builder also ran an actual PSD conversion and downloaded the PNG in Edge at 360 px with no horizontal overflow. That visual check is manual rather than a repeatable automated test.

The 40 MP ceiling was exercised with both a layerless RGB PSD and a layered RGB PSD in a network-disabled 3 GiB container; each produced a valid 8000-by-5000 PNG. The final Docker build, OCR and translation smoke checks, and the mobile browser conversion also pass.
