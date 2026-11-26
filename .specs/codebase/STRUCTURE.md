# Project Structure

**Root:** `d:\code\i-love-open-converter`

## Directory Tree

```text
i-love-open-converter/
├── .github/workflows/       # CI (ruff, pytest, container builds) & image publishing
├── .specs/                  # Architecture decisions, codebase docs, and feature specs
│   ├── adr/
│   ├── codebase/
│   ├── features/
│   └── project/
├── docker/                  # Container entrypoints & runtime configuration
├── docs/                    # Product screenshots and social preview assets
├── scripts/                 # CI coverage skip verification & container publishing
├── src/i_love_open_converter/
│   ├── static/
│   │   ├── css/app.css      # Unified OKLCH design system & Studio layout
│   │   ├── fonts/           # Bundled DejaVu TTF fonts
│   │   └── js/              # Home Studio controller (app.js) + 18 tool scripts
│   ├── templates/           # Home catalog/Studio (index.html) + 18 tool templates
│   ├── main.py              # FastAPI routes, upload limits, preview endpoints
│   ├── worker.py            # Background job processor
│   └── *_ops.py / *_worker.py # Domain conversion & sandboxed workers
└── tests/                   # API, format matrix, coverage, and Playwright UI tests
```
