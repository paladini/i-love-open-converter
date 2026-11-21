# Review

**Verdict:** The implementation covers the approved local background-removal scope. The full test suite (156 tests), Ruff, JavaScript syntax check, and TLC plan validation pass. I found no demonstrated runtime or UI defect. Two regression-coverage gaps remain for explicit plan guarantees.

## Request, sentence by sentence

> “Remova rapidamente fundos de imagens com alta precisão. Detecte instantâneamente objetos e corte o fundo com facilidade.”

The catalog activates “Remover fundo” and offers one local U2NetP segmentation job. The UI and README say quality depends on the image and do not promise perfect edges. That is a useful limit disclosure for a lightweight CPU model; no result-quality benchmark or accuracy claim was tested.

> Activate the existing “Remover fundo” image tool. Let a visitor submit one supported static image and download a PNG cutout with a transparent background. All image inference runs on the self-hosted server with a locally installed lightweight model; image bytes are not sent to a cloud service.

The shared image job flow accepts one static image and returns an RGBA PNG. Inspection found the implementation calls local `rembg.remove` with a cached U2NetP session; the only network URL in the feature is for retrieving model weights, not image content. Compose isolates the worker with `network_mode: none`.

> The first version uses the U2NetP general salient-object model through rembg's CPU runtime. It does not promise perfect edges or support user-drawn masks, batch jobs, alternate backgrounds, or cloud inference. The model weights and their separate license must be disclosed and attributed.

The implementation pins `rembg[cpu]` and ONNX Runtime, documents edge limitations, and includes the U-2-Net Apache-2.0 license and source attribution. The Docker build downloads the model and verifies SHA-256 before copying it into the final image. `U2NET_HOME=/opt/u2net` and `/opt/u2net/u2netp.onnx` match rembg's supported legacy flat model path, so the isolated worker can find the preloaded model.

## Criteria and test strength

| Criterion | Evidence and regression strength |
| --- | --- |
| S1.1: localized tool, single-image picker, PNG and 40 MP disclosure, local notice | `test_home_page_has_image_and_pdf_groups_and_local_assets` checks the active card and bilingual strings. Browser review showed a single-file input, hidden output-format selector (PNG is disclosed in the card), and local quality notice in PT-BR and English. |
| S1.2: queue one job and return same oriented dimensions with RGBA PNG | `test_background_removal_creates_transparent_png_and_rejects_other_formats` checks PNG MIME, RGBA, alpha and size with a stubbed mask. It does not test EXIF-rotated input, so it would pass if orientation handling regressed. Finding P2 below. |
| S1.3: cached CPU U2NetP, no external image service | `test_background_removal_uses_one_cached_local_session` stubs rembg and verifies the U2NetP session is created once and reused. It would fail if the model choice or session cache changed. Code inspection confirms only the local rembg inference API is called. |
| S1.4: model is included for isolated Docker worker, no runtime download | Dockerfile pins the model URL, checks its SHA-256, copies it to `/opt/u2net`, and sets `U2NET_HOME`; Compose retains `network_mode: none`. I confirmed rembg recognizes that flat path. No automated test protects this packaging contract; finding P2 below. |
| S1.5: reject missing/multiple input, unsupported settings, and >40 MP before job | API tests assert 422 and zero jobs for missing/multiple files and oversized dimensions; the output-format case asserts a job is not created. Existing shared image API tests cover invalid content and extensions. |
| S1.6: inference failure leaves no output and download returns 409 | `test_background_removal_worker_failure_has_no_partial_output` asserts failed state, 409 download, and no file. |
| S1.7: mobile controls remain reachable without overflow | At the 360 px viewport override, PT-BR and English both had `documentElement.scrollWidth=345`; input was single-file and output selector hidden. The browser reported `innerWidth=361` for the 360 px override, so this is a near-exact mobile check. |
| S1.8: disclose quality limits in UI and docs | The localized UI note and both README entries state that edge quality depends on the image and is not guaranteed. Static UI assertions cover the localized hint; manual review confirmed both visible notes. |

## Findings

- **[P2] Add an EXIF-orientation regression test for background removal.** Criterion S1.2 promises the oriented source dimensions. `process_image` currently applies `ImageOps.exif_transpose` before removal, but the background-removal processing test uses only an unrotated 8x6 image. A regression that removed or reordered the transpose would pass the current feature tests. Add a rotated EXIF fixture and assert the PNG has the oriented dimensions.
- **[P2] Protect the offline model packaging contract with a regression check.** Criterion S1.4 depends on the Docker model path, `U2NET_HOME`, checksum, and network-isolated worker agreeing. The configuration currently agrees with rembg's lookup path, but the tests do not inspect this relationship. A Dockerfile path or environment-variable change could leave the worker trying to download weights with networking disabled. Add a focused check that verifies the model destination, checksum verification, environment path, and isolated worker contract remain aligned.

## Review setup

- Full pytest suite: passed (156 tests).
- `ruff check .`, `node --check src/i_love_open_converter/static/js/app.js`, and TLC `validate_plan.py`: passed.
- Browser at `http://127.0.0.1:8795/`, isolated `.specs/features/image-background-removal/review-data`, stopped and cleaned after review.
- No captures were listed by the plan; therefore there was no capture comparison.
- No code, commits, pushes, or app data were changed by the reviewer.

## Author response

- **[P2] EXIF orientation coverage:** addressed in the one fix pass. A rotated JPEG fixture verifies the inference input and RGBA PNG use the EXIF-oriented width and height.
- **[P2] Offline model packaging coverage:** addressed in the one fix pass. A deployment regression test checks the pinned model URL and SHA-256, Docker model destination and `U2NET_HOME`, and the worker's `network_mode: none` setting together.
