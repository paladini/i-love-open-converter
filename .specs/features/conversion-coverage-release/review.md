# Conversion coverage and release maturity review

**Verdict: Request changes.** The inspected implementation matches the stage 6 behavior in the approved plan for the paths reviewed, and the 360 px UI check passed with stubbed job responses. The acceptance evidence is incomplete: the rejection test does not verify that no job is created, and the required 360 px behavior has no automated regression test. Focused tests could not be run in this environment.

## Scope

This review assessed stage 6 of the approved conversion coverage plan: static GIF output, bilingual capability documentation, deployment settings parity, and the 360 px browser flow. PR publication and merge are subsequent workflow steps and were not part of this code review.

## Acceptance criteria

| Criterion | Review |
| --- | --- |
| AC1: generic static raster conversion offers JPEG, PNG, GIF, WebP; one frame per input | `main.py:1205-1225` accepts GIF only for `image.convert`; `image_ops.py:495-497` writes GIF; the UI selector showed all four outputs in the live app. The single-file API test asserts GIF MIME, name, dimensions, and one frame (`tests/test_api.py:1704-1723`). Its assertions would fail for those incorrect results, but the test was not executed in this environment. |
| AC2: single GIF artifact and batch ZIP with one GIF per input | The tests assert the output name/type and one frame for the single result, and the ordered ZIP entries and one frame per entry for a batch (`tests/test_api.py:1704-1751`). These checks would fail for the named output-contract errors; execution was blocked. |
| AC3: preserve animated JPG-to-GIF and reject unsupported outputs without creating a job | Existing JPG tests inspect animated output behavior, including ordered multi-frame output and one-frame output (`tests/test_image_from_jpg.py:72-115`). The new non-GIF-operation test asserts 422 (`tests/test_api.py:1754-1765`), and route validation occurs before `create_job` (`main.py:1215-1225`, `1900-1906`). However, that test does **not** inspect the database job count, so it would still pass if a job were created before a 422 response. See finding F1. |
| AC4: localized guide, accurate hint, GIF limited to the two supported tools | The home-page test checks the translated strings and GIF markup; the JPG catalog test checks both allowed-format branches (`tests/test_api.py:1031-1068`, `tests/test_image_from_jpg.py:225-240`). Those are source-text checks, not a browser interaction test. The live app showed the guide, hint, and correct selector in PT-BR and English. |
| AC5: bilingual matrix contains supported pairs and constraints, with no unsupported paths | The current README tables were manually compared with the documented operation paths and limits and appear accurate for this scope. The matrix test checks several required rows, output terms, limits, and exact RAW extensions (`tests/test_release_docs.py:30-78`), but it does not detect every unsupported extra pair or inaccurate per-format constraint. See finding F2. |
| AC6: repository checks catch stale capability inventory, omitted GIF, and config drift | The inventory assertions fail if RAW or offline translation are marked planned; matrix assertions catch generic GIF omission; the config test compares `.env.example`, Compose substitutions, and documented values (`tests/test_release_docs.py:81-126`). The “only shipped paths” portion remains under-enforced as described in F2. |
| AC7: 360 px PT-BR and English guide/catalog/controls/status/result work without horizontal overflow | No automated 360 px test was added. In the live browser at 360 x 900, both locales rendered the guide and catalog, the generic selector offered four outputs, and `documentElement.scrollWidth` equaled its client width (345 px after the vertical scrollbar). I intercepted the submit and status responses in the browser and verified the localized completed state, `review.gif`, and its download link in both languages. The POST was handled by the browser stub, so it did not create or modify app data. |
| AC8: bilingual Compose quick start is clear and preserves stored files | The docs test checks the config table, copy command, `up`, `ps`, logs, and `down` guidance and rejects `down -v` (`tests/test_release_docs.py:112-126`). It checks text and settings parity; it does not execute Docker Compose. The current commands and fixed `./data:/data` volume are consistent on inspection. |

## Findings

### F1 — Rejection test misses the no-job guarantee (P2)

`tests/test_api.py:1754-1765` only checks for a 422 response and error code. The AC additionally requires no conversion job to be created. The test would not catch a regression that creates a row and then returns 422. The current endpoint validates the format before reaching `create_job`, so this is a coverage gap rather than an observed behavior defect.

### F2 — Mobile acceptance is not protected by an automated test; capture comparison unavailable (P2)

The home-page and JPG-catalog tests inspect source strings, but no test opens both locales at the required 360 px viewport and checks the guide, catalog, controls, status, download result, and overflow together. The referenced `.specs/features/conversion-coverage-release/captures/` path also does not exist, including when searching ignored files, so the requested per-capture visual comparison was impossible. The independent live-browser check passed at 360 x 900 with a stubbed job response, but it does not prevent future regressions or substitute for the missing reference comparison.

## Verification limits and state

- The focused `uv run pytest ...` attempt failed before test collection because `uv` could not update the locked local `.venv` package (`pydantic_core/_pydantic_core.cp314-win_amd64.pyd`: access denied). No test pass is claimed.
- The app's disposable data was not changed. The browser POST and status responses were intercepted; the recorded fake `review.gif` result was never sent to the app.
- The only uncommitted source-control change observed was the status-only edit in `plan.md` (`Review: pending` to `Review: sent at 5c27e8d`). No implementation changes were made during review.
