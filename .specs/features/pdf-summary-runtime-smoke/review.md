# Review

**Verdict:** The smoke check uses the final Python 3.14 virtual environment and fails the image build when local summary inference returns no text. Network denial is not guaranteed for the full process.

## Finding

- **P2 — The build step does not isolate the summary inference from network access.** `docker/summary-smoke.py:12-13` replaces Python's `socket.create_connection` and `socket.socket.connect`, but the Dockerfile runs the script in a normal network-enabled `RUN` instruction (`Dockerfile:142-145`). These monkeypatches do not prevent native code from opening a connection or Python code from using another socket entry point such as `connect_ex`. The request requires network connections to be blocked during this check. Run the summary smoke step with BuildKit's `RUN --network=none` (separately from any other smoke steps if necessary), or use an equally strong isolation mechanism.

## Checks

- Confirmed the Dockerfile copies the summary model to `/opt/local-summary-model`, sets `LOCAL_SUMMARY_MODEL_DIR`, installs dependencies into `.venv`, and runs the smoke with `/app/.venv/bin/python` after installing the application. This is the final Python 3.14 runtime stage.
- Confirmed `_abstractive_summary` loads the local tokenizer and CTranslate2 translator and invokes generation. A missing model or handled load/inference failure returns `None`; the smoke exits nonzero when the result is empty.
- No Docker build or tests were run, per the review instructions.
