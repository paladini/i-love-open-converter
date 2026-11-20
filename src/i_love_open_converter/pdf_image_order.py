from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.generic import ContentStream, IndirectObject


class ImageOrderError(Exception):
    """The drawing sequence cannot be established safely."""


def image_order(source: Path) -> list[list[int]]:
    reader = PdfReader(source)

    def walk(content: Any, resources: Any, stack: frozenset[int], depth: int) -> list[int]:
        if depth > 32:
            raise ImageOrderError
        result: list[int] = []
        if content is None:
            return result
        for operands, operator in ContentStream(content, reader).operations:
            if operator == b"INLINE IMAGE":
                result.append(0)
            elif operator == b"Do" and operands:
                xobjects = resources.get("/XObject") if resources else None
                if xobjects is None:
                    raise ImageOrderError
                xobjects = xobjects.get_object()
                reference = xobjects.raw_get(operands[0])
                obj = reference.get_object()
                subtype = obj.get("/Subtype")
                if subtype == "/Image":
                    result.append(reference.idnum if isinstance(reference, IndirectObject) else 0)
                elif subtype == "/Form":
                    identifier = (
                        reference.idnum if isinstance(reference, IndirectObject) else id(obj)
                    )
                    if identifier in stack:
                        raise ImageOrderError
                    nested_resources = obj.get("/Resources", resources)
                    if nested_resources is not None:
                        nested_resources = nested_resources.get_object()
                    result.extend(walk(obj, nested_resources, stack | {identifier}, depth + 1))
        return result

    def page_images(page: Any) -> list[int]:
        result = walk(page.get_contents(), page.get("/Resources"), frozenset(), 0)
        for reference in page.get("/Annots", []):
            annotation = reference.get_object()
            if int(annotation.get("/F", 0)) & (1 | 2 | 32):
                continue
            appearances = annotation.get("/AP")
            if not appearances:
                continue
            appearance = appearances.get_object().get("/N")
            if not appearance:
                continue
            appearance = appearance.get_object()
            if appearance.get("/Subtype") != "/Form":
                appearance = appearance.get(annotation.get("/AS"))
                if not appearance:
                    continue
                appearance = appearance.get_object()
            result.extend(walk(appearance, appearance.get("/Resources"), frozenset(), 0))
        return result

    try:
        return [page_images(page) for page in reader.pages]
    except ImageOrderError:
        raise
    except Exception as exc:
        raise ImageOrderError from exc
