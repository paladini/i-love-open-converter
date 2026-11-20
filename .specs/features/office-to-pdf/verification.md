# Office conversion verification

Generate synthetic documents with `uv run --with python-docx --with python-pptx --with openpyxl python .specs/features/office-to-pdf/create-probe.py`. Build the project image, then mount the repository read-only at `/workspace` into that image and run `run-probe.py` with `--network none`, `--user 1000:1000`, and `OFFICE_NETWORK_ISOLATED=1`. The probe checks document text in the resulting PDFs for all six advertised extensions and checks that the sandbox denies access to a different job's file. The generated `probe-files` directory is disposable test data.
