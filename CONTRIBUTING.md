# Contributing

Thanks for helping improve I Love Open Converter.

Please read the [Code of Conduct](CODE_OF_CONDUCT.md), [Support guide](SUPPORT.md), and [Security policy](SECURITY.md) before participating. Suspected vulnerabilities must be reported privately, not through a public issue.

## Development setup

Requirements: Python 3.14 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --all-groups
uv run uvicorn i_love_open_converter.main:app --app-dir src --reload
```

Open <http://127.0.0.1:8000> while developing. Set `DATA_DIR` to a temporary or ignored local directory if you do not want development jobs in `./data`.

## Checks

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Add tests for behavior changes. Keep file processing local and avoid telemetry, external runtime requests, or unsupported file claims.

## Pull requests

Keep changes focused, describe user-visible behavior, include reproduction steps for bug fixes, and update documentation when an operation or configuration changes. By contributing, you agree that contributions are distributed under AGPL-3.0-only.
