# Independent review: Local abstractive PDF summary

## Findings

### [P2] Final reduction can submit text above the model input limit

[`pdf_ops.py`](../../src/i_love_open_converter/pdf_ops.py#L142) processes at most four reduction rounds, then joins any remaining chunks and sends them directly to the model at [line 150](../../src/i_love_open_converter/pdf_ops.py#L150). Each chunk can contain 440 SentencePiece tokens, so two or more remaining chunks can exceed FLAN-T5's input limit after the prompt is added. CTranslate2 may reject that input; the broad fallback then silently switches to extractive output. Keep reducing until one chunk remains, or split/reduce the final joined text under the same token budget.

### [P2] Converter build does not exercise runtime inference

The feature depends on successful model loading and `translate_batch` inference at [`pdf_ops.py`](../../src/i_love_open_converter/pdf_ops.py#L90) and [lines 122–132](../../src/i_love_open_converter/pdf_ops.py#L122). The reported builder-stage success establishes that the pinned checkpoint converts and the 76 MB artifact contains the expected files, but it does not establish that the Python 3.14 runtime can load the converted model and generate text. The current fallback catches several failures and can mask this path as a successful extractive result. Add a small inference smoke check in the image/CI workflow before treating the abstractive acceptance criterion as verified.

## Reviewed areas

- Docker builder pins FLAN-T5-small revision `0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab`, installs the CPU-only PyTorch wheel, and pins CTranslate2, SentencePiece, and Transformers. The converter writes to `/opt/local-summary-model`; `spiece.model` is fetched from the same revision. The final image copies that directory and sets `LOCAL_SUMMARY_MODEL_DIR`; it does not copy the builder's Python environment. This is consistent with the CPU-only/local-runtime design.
- Runtime loading expects `spiece.model` and a CTranslate2 model directory and explicitly selects `device="cpu"`. The versions in the application dependencies are pinned and the lockfile includes Linux x86_64 and aarch64 CTranslate2/SentencePiece wheels for Python 3.14. This matches the intended inference API at inspection time.
- PDF limits are enforced while extracting selectable text: 100 pages, 100,000 characters, and 2,000 sentences. Missing model files, import/load errors, and common inference errors return `None`, preserving the extractive fallback. Generated and fallback outputs identify their mode; generated output also asks the reader to verify the source.
- The tool page and both README summaries describe local processing, extractive fallback, OCR for scans, and source verification. The project UI's existing language preference defaults to Portuguese; the feature strings are present in both English and Brazilian Portuguese. The user separately directed that README screenshots/interface examples remain English by default; this feature's docs do not add screenshots.
- The notices identify the FLAN-T5 source, pinned revision, Apache-2.0 license, and bundled license file. The model inference code has no network calls; build-time downloads fetch only model/dependency artifacts. Document text remains in the local worker flow.

## Scope

Read-only review, except for this report. No tests or builds were run. The `summary-model-builder` success and 76 MB artifact size are taken from the task context, not independently repeated.

## Fix pass

- Resolved the first finding: recursive reduction now permits up to eight rounds and never joins multiple chunks into an oversized final model input. If it cannot reduce to one chunk, it falls back to the existing extractive summary.
- The complete Docker image now builds successfully with Python 3.14. The final image contains the 76 MB model, sets `LOCAL_SUMMARY_MODEL_DIR`, and excludes PyTorch and Transformers. Existing OCR and translation image smoke checks also pass.
- Runtime model loading and generation were not exercised in this fix pass. The new summarization path therefore remains unverified at inference time; CI's current checks do not cover that path. No tests were added or run.
