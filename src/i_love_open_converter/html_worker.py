"""Render one local HTML file to PDF inside a Landlock and resource-bounded child."""

from __future__ import annotations

import os
import resource
import sys
from pathlib import Path

from .office_sandbox import restrict


def main(root: Path, source: Path, destination: Path) -> int:
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    try:
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))
        restrict(root, allow_app=True)
    except (OSError, ValueError):
        return 77

    from weasyprint import HTML
    from weasyprint.urls import FatalURLFetchingError, URLFetcher

    from .html_ops import MAX_HTML_PAGES, allowed_html_resource

    class DataOnlyFetcher(URLFetcher):
        def fetch(self, url: str, headers: dict[str, str] | None = None):
            if not allowed_html_resource(url):
                raise FatalURLFetchingError("Only embedded data URI resources are supported")
            return super().fetch(url, headers)

    try:
        document = HTML(filename=str(source), url_fetcher=DataOnlyFetcher()).render()
        if not 1 <= len(document.pages) <= MAX_HTML_PAGES:
            return 2
        document.write_pdf(str(destination))
    except FatalURLFetchingError:
        return 4
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])))
