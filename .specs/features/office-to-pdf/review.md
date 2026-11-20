# Independent review

Verdict: changes required. The user's request asks to keep implementing the whole application and open PRs; this plan explicitly covers only Office-to-PDF and does not establish completion of the broader roadmap.

## Finding

1. **P1 - A small OOXML upload can expand without a resource bound.** `office_ops.validate_office()` checks the number and names of ZIP entries and encryption flags, but not their individual or aggregate uncompressed sizes or compression ratios. `convert_office()` then hands the upload to LibreOffice with a 120-second timeout, while the worker has no memory or disk limit. I created, in a temporary directory inside the repository, a `.docx` ZIP of 130,712 bytes with a `word/document.xml` entry declaring 134,217,728 uncompressed bytes; `validate_office()` accepted it. Larger inputs fit under the upload-byte limit and can cause substantial memory or temporary-disk consumption before the timeout, affecting this unauthenticated self-hosted service and other jobs. Bound the expanded package and the conversion resources; add regression coverage for high-expansion files. The temporary file was removed by its context manager.

## Criteria and test evidence

1. Each family has a route and localized page with a single-file input, polling and download. I inspected the running Word page read-only; the plan cites no captures or capture sizes, so none were available for comparison. `test_office_job_and_download` checks route status but does not exercise the page interaction or localized states.
2. `test_office_job_and_download` checks each operation and downloaded PDF but replaces conversion with a fake, so it cannot detect a broken LibreOffice invocation or unsupported real documents. The committed container probe exercises all six advertised extensions with actual conversions and text assertions, but it is not part of the ordinary pytest run.
3. `test_office_rejects_wrong_extension_and_multiple_files` would detect those two regressions; `test_office_rejects_mismatched_and_invalid_container` detects the two specific container cases tested. No automated test exercises password-protected input, a real converter failure, timeout, or absence of a published artifact after those failures.
4. The Compose worker has `network_mode: none`. The probe checks network interfaces and a denied read from another job, but no test exercises macro execution. A timeout and per-job profile are present; no automated test checks their behavior on a real adversarial document. The high-expansion finding above limits the claim of bounded processing.
5. `test_office_isolation_fails_closed` would detect conversion when its mocked `office_isolated()` returns false and checks the failed status and no download. It does not test a real missing executable, Landlock rule failure, or timeout.
6. Both READMEs list the formats, dependency, Linux isolation requirements and fidelity limitations. The existing test suite covers many preexisting operations, but this review did not independently run all those operations inside the newly network-isolated worker.

The running application's data was not changed. No feature captures were present or cited; the browser check was read-only.
