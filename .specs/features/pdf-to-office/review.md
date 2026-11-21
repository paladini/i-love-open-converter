# Independent review

Verdict: changes required. The user's request is to continue implementing the whole application and open PRs; this plan delivers only PDF-to-Word and retains PDF-to-PowerPoint and PDF-to-Excel for later work. The complete objective is not yet finished.

## Findings

1. **P1 - Standalone PDF-to-Word jobs are not prevented from accessing the network.** Criterion 4 and the plan's shape require the converter to run without network access. `compose.yaml` supplies `network_mode: none`, but `pdf_ops.py` starts `word_worker.py` directly, and neither verifies the worker's network namespace nor confines network access. On this Windows host, the documented direct Python worker environment has non-loopback interfaces; I independently ran `tests/test_pdf_to_word.py` successfully in that environment. The child therefore inherits the host network even though the same conversion succeeds. I did not observe a document being transmitted or prove that the current library makes an external request; the demonstrated problem is that the required isolation boundary is absent for standalone workers. The existing `office_isolated()` guard applies to Office-to-PDF only. No Word test checks this rule.

2. **P2 - The standalone Windows conversion subprocess has no memory, CPU or output-file resource limits.** `word_worker.py` installs `RLIMIT_AS`/`RLIMIT_DATA`, `RLIMIT_CPU` and `RLIMIT_FSIZE` only inside `if sys.platform == "linux"`. Windows nevertheless executes the conversion normally, as shown by the passing targeted tests. The parent timeout and page-area check do not bound native image decompression, memory allocation or individual output size. This differs from the unqualified bounded-child requirement and from the documentation saying the same resource limits apply. I did not run a memory-exhaustion test on the user's host. No test verifies the limits on Windows or fails when those calls are skipped.

## Criteria and tests

1. The catalog link, bilingual upload page, polling, status text and download control exist. I opened the initial page against a throwaway local application data directory; no captures or capture sizes are present or cited for this feature. The test checks route availability but does not automate browser interaction or language changes.
2. `test_pdf_to_word_has_editable_text_in_order` performs a real conversion and inspects editable DOCX paragraphs on two pages; it detects missing or reordered sample text. `test_pdf_to_word_retains_detectable_table_and_image` checks a detected table cell and at least one image. These examples do not establish fidelity for arbitrary complex PDFs, which the plan explicitly does not promise.
3. The invalid, multiple and encrypted input cases are tested. The oversized-page test verifies failure and no download. There is no test forcing a timeout or testing a corrupted generated DOCX and verifying no artifact.
4. The code disables multi-process conversion and documents lack of OCR, but standalone network and resource isolation are not enforced as described above. The tests do not exercise either platform boundary.
5. I ran `uv run pytest -q tests/test_pdf_to_word.py` on Windows: all four tests passed. The AMD64 image conversion was reported by the implementer; the ARM64 build was still running during this review. I did not independently verify either Linux runtime or rerun all existing operations.
6. Both READMEs name the supported operation, `pdf2docx`, its upstream maintenance status, and fidelity and resource limits. The standalone Windows resource-limit qualification is missing, as described above.

The review used a synthetic PDF in a temporary directory inside the repository and a throwaway data directory, both removed. It did not change existing application data.

## Fix pass

Both findings were addressed. `pdf.to_word` now refuses to start unless it runs on Linux, carries the worker isolation setting, and sees only the loopback interface. The Compose worker already sets that setting and uses `network_mode: none`; unsupported Windows or network-attached workers report `word_unavailable`. The README now explains this deployment requirement. Tests cover the unavailable result and the Linux, attestation, and interface checks.

Verification after the fix: the full Windows pytest suite passed (108 tests); Ruff, JavaScript syntax, `git diff --check`, and the TLC plan and commit validators passed. The final AMD64 runtime image was rebuilt and converted a sample PDF to a DOCX with networking disabled. The existing ARM64 runtime image converted with the updated source bind-mounted in the same isolated configuration. A connected worker was refused, an oversized page failed safely, and a browser upload/download succeeded through the isolated worker. Browser verification was done in the disposable local Docker app at the feature route.

The Windows conversion tests mock only the isolation guard so they can test the document conversion engine without pretending Windows is an accepted deployment. Resource limits for the conversion remain enforced by the Linux worker; Windows direct conversion now fails closed. The review's broader roadmap observation remains valid and is the reason this feature is only one stage of the still-active application goal.
