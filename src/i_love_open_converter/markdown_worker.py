"""Run PDF layout extraction separately so a failure cannot kill the job worker."""

from __future__ import annotations

import base64
import os
import platform
import re
import sys
from pathlib import Path


def main(source: Path, output: Path) -> None:
    # Bound native layout allocations in the Linux production worker.
    if sys.platform == "linux":
        import resource

        # ONNX sizes its thread pools from CPU affinity; bound them before applying
        # the address-space limit so many thread stacks cannot exhaust it at startup.
        if platform.machine().lower() != "aarch64":
            available = sorted(os.sched_getaffinity(0))
            os.sched_setaffinity(0, set(available[:2]))
        if platform.machine().lower() == "aarch64":
            resource.setrlimit(resource.RLIMIT_DATA, (1536 * 1024**2, 1536 * 1024**2))
        else:
            resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"

    import onnxruntime
    import pymupdf

    onnxruntime.disable_telemetry_events()
    original_session = onnxruntime.InferenceSession

    def bounded_session(*args, **kwargs):
        options = kwargs.get("sess_options") or onnxruntime.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        kwargs["sess_options"] = options
        return original_session(*args, **kwargs)

    onnxruntime.InferenceSession = bounded_session
    assets: list[Path] = []
    total_image_bytes = 0
    chunks: list[str] = []
    with pymupdf.open(source) as document:
        for page in document:
            # A 150-dpi rendering must not exceed 16 megapixels, even for tiny input PDFs.
            width = page.rect.width * 150 / 72
            height = page.rect.height * 150 / 72
            if width <= 0 or height <= 0 or width * height > 16_000_000:
                raise ValueError("PDF page exceeds the rendering limit")

        for index in range(document.page_count):
            markdown = document.to_markdown(
                pages=[index], use_ocr=False, embed_images=True, filename="document"
            )
            if not isinstance(markdown, str):
                raise ValueError("Invalid Markdown output")

            def store_image(match: re.Match[str]) -> str:
                nonlocal total_image_bytes
                raw = base64.b64decode(match.group(2), validate=True)
                total_image_bytes += len(raw)
                if len(assets) >= 200 or total_image_bytes > 256 * 1024 * 1024:
                    raise ValueError("Markdown images exceed the output limit")
                path = output / f"image-{len(assets) + 1:03d}.png"
                path.write_bytes(raw)
                assets.append(path)
                return f"![{match.group(1)}]({path.name})"

            chunks.append(re.sub(
                r"!\[([^\]]*)\]\(data:image/png;base64,([A-Za-z0-9+/=]+)\)",
                store_image,
                markdown,
            ))
            if sum(len(chunk) for chunk in chunks) > 256 * 1024 * 1024:
                raise ValueError("Markdown text exceeds the output limit")
    (output / "document.md").write_text("\n\n".join(chunks), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
