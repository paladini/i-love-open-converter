from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pymupdf

from .ocr_ops import MAX_OCR_PAGES
from .pdf_ops import InvalidPdfError, inspect_pdf


def detect_pdf_form_fields(path: Path) -> list[dict[str, Any]]:
    inspect_pdf(path)
    with pymupdf.open(path) as document:
        if not 1 <= document.page_count <= MAX_OCR_PAGES:
            raise InvalidPdfError
        suggestions: list[dict[str, Any]] = []
        for page_index, page in enumerate(document):
            dpi = min(
                120, max(36, int(72 * (1_000_000 / (page.rect.width * page.rect.height)) ** 0.5))
            )
            text_page = page.get_textpage_ocr(language="eng+por", dpi=dpi, full=True)
            words = page.get_text("words", textpage=text_page, sort=True)
            for word in words:
                raw_label = str(word[4]).strip()
                label = raw_label.rstrip(":")
                if (
                    not raw_label.endswith(":")
                    or not label
                    or len(label) > 60
                    or not any(char.isalpha() for char in label)
                ):
                    continue
                rect = pymupdf.Rect(word[:4]) * page.rotation_matrix
                width = min(max(100, rect.width * 3), page.rect.width - rect.x1 - 8)
                if width < 24 or rect.y1 + 5 >= page.rect.height:
                    continue
                y1 = min(page.rect.height - 2, max(rect.y1 + 18, rect.y0 + 18))
                suggestions.append(
                    {
                        "type": "text",
                        "name": f"field_{page_index + 1}_{len(suggestions) + 1}",
                        "page": page_index + 1,
                        "rect": [rect.x1 + 6, rect.y0, rect.x1 + 6 + width, y1],
                        "label": label,
                    }
                )
                if len(suggestions) >= 200:
                    break
            if len(suggestions) >= 200:
                break
            existing_boxes = [
                pymupdf.Rect(*item["rect"])
                for item in suggestions
                if item["page"] == page_index + 1
            ]
            for drawing in page.get_drawings():
                for item in drawing.get("items", []):
                    if item[0] == "re":
                        shape = pymupdf.Rect(item[1])
                        if not (
                            12 <= shape.width <= 20
                            and 10 <= shape.height <= 20
                            and 0.75 <= shape.width / shape.height <= 1.25
                        ):
                            continue
                        rect = shape * page.rotation_matrix
                        if any(rect.intersects(old) for old in existing_boxes):
                            continue
                        suggestions.append(
                            {
                                "type": "checkbox",
                                "name": f"checkbox_{page_index + 1}_{len(suggestions) + 1}",
                                "page": page_index + 1,
                                "rect": [rect.x0, rect.y0, rect.x1, rect.y1],
                                "label": "Checkbox",
                            }
                        )
                        existing_boxes.append(rect)
                    elif item[0] == "l":
                        start, end = item[1], item[2]
                        if (
                            abs(start.y - end.y) > 1.5
                            or not 60 <= abs(end.x - start.x) <= page.rect.width * 0.6
                        ):
                            continue
                        line_rect = pymupdf.Rect(
                            min(start.x, end.x), start.y - 10, max(start.x, end.x), start.y + 10
                        )
                        rect = line_rect * page.rotation_matrix
                        if any(rect.intersects(old) for old in existing_boxes):
                            continue
                        suggestions.append(
                            {
                                "type": "text",
                                "name": f"field_{page_index + 1}_{len(suggestions) + 1}",
                                "page": page_index + 1,
                                "rect": [rect.x0, rect.y0, rect.x1, rect.y1],
                                "label": "Blank line",
                            }
                        )
                        existing_boxes.append(rect)
                    if len(suggestions) >= 200:
                        break
                if len(suggestions) >= 200:
                    break
        return suggestions


if __name__ == "__main__":
    print(json.dumps(detect_pdf_form_fields(Path(sys.argv[1]))))
